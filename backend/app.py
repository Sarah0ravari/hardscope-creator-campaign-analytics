import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

from scraper import fetch_channel_videos, fetch_videos_statistics

DB_PATH = Path(__file__).parent / "data.db"
DEFAULT_PLATFORM = "youtube"
VALID_SORT_FIELDS = {
    "name": "name",
    "videos": "videos",
    "total_views": "total_views",
    "avg_views": "avg_views",
    "engagement_rate": "engagement_rate",
    "latest_publish_date": "latest_publish_date",
}


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS creators (
            id INTEGER PRIMARY KEY,
            platform TEXT NOT NULL,
            channel_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'youtube_data_api',
            campaign_label TEXT,
            last_ingested_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY,
            creator_id INTEGER NOT NULL,
            video_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            published_at TEXT NOT NULL,
            views INTEGER NOT NULL DEFAULT 0,
            likes INTEGER,
            comments INTEGER,
            fetched_at TEXT NOT NULL,
            FOREIGN KEY(creator_id) REFERENCES creators(id)
        )
        """
    )
    _ensure_column(cur, "creators", "source", "TEXT NOT NULL DEFAULT 'youtube_data_api'")
    _ensure_column(cur, "creators", "campaign_label", "TEXT")
    _ensure_column(cur, "creators", "last_ingested_at", "TEXT")
    conn.commit()
    conn.close()


def _ensure_column(cursor, table_name, column_name, definition):
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing = {row[1] for row in cursor.fetchall()}
    if column_name not in existing:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


app = Flask(__name__)
CORS(app)
init_db()


def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_video_filters(start, end):
    clauses = []
    params = []
    if start:
        clauses.append("published_at >= ?")
        params.append(start)
    if end:
        clauses.append("published_at <= ?")
        params.append(end)
    return clauses, params


def _creator_query_results(
    platform=DEFAULT_PLATFORM,
    start=None,
    end=None,
    min_views=0,
    min_engagement=0.0,
    sort_by="total_views",
    sort_dir="desc",
    limit=100,
):
    video_filters, video_params = _build_video_filters(start, end)
    where_sql = f"WHERE {' AND '.join(video_filters)}" if video_filters else ""
    order_sql = VALID_SORT_FIELDS.get(sort_by, "total_views")
    order_direction = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
    query = f"""
    WITH filtered_videos AS (
        SELECT *
        FROM videos
        {where_sql}
    ),
    creator_rollup AS (
        SELECT
            c.id,
            c.platform,
            c.channel_id,
            c.name,
            c.source,
            c.campaign_label,
            c.last_ingested_at,
            COUNT(fv.id) AS videos,
            COALESCE(SUM(fv.views), 0) AS total_views,
            COALESCE(AVG(fv.views), 0) AS avg_views,
            COALESCE(SUM(COALESCE(fv.likes, 0)), 0) AS total_likes,
            COALESCE(SUM(COALESCE(fv.comments, 0)), 0) AS total_comments,
            MAX(fv.published_at) AS latest_publish_date
        FROM creators c
        LEFT JOIN filtered_videos fv ON fv.creator_id = c.id
        WHERE c.platform = ?
        GROUP BY c.id
    )
    SELECT
        *,
        CASE
            WHEN total_views > 0 THEN ROUND(((total_likes + total_comments) * 100.0) / total_views, 2)
            ELSE 0
        END AS engagement_rate
    FROM creator_rollup
    WHERE total_views >= ?
      AND (
        CASE
            WHEN total_views > 0 THEN ROUND(((total_likes + total_comments) * 100.0) / total_views, 2)
            ELSE 0
        END
      ) >= ?
    ORDER BY {order_sql} {order_direction}, total_views DESC
    LIMIT ?
    """
    params = [*video_params, platform, min_views, min_engagement, limit]
    conn = get_db_conn()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def _analytics_overview(creators):
    total_creators = len(creators)
    total_videos = sum(row["videos"] for row in creators)
    total_views = sum(row["total_views"] for row in creators)
    total_likes = sum(row["total_likes"] for row in creators)
    total_comments = sum(row["total_comments"] for row in creators)
    avg_views_per_creator = round(total_views / total_creators, 2) if total_creators else 0
    avg_views_per_video = round(total_views / total_videos, 2) if total_videos else 0
    avg_engagement_rate = round(
        sum(row["engagement_rate"] for row in creators) / total_creators, 2
    ) if total_creators else 0
    top_creator = max(creators, key=lambda row: row["total_views"], default=None)
    at_risk = [
        row for row in creators
        if row["videos"] > 0 and (row["engagement_rate"] < 1.5 or row["avg_views"] < 25000)
    ]
    return {
        "total_creators": total_creators,
        "total_videos": total_videos,
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "avg_views_per_creator": avg_views_per_creator,
        "avg_views_per_video": avg_views_per_video,
        "avg_engagement_rate": avg_engagement_rate,
        "top_creator": {
            "name": top_creator["name"],
            "channel_id": top_creator["channel_id"],
            "total_views": top_creator["total_views"],
            "engagement_rate": top_creator["engagement_rate"],
        } if top_creator else None,
        "at_risk_creators": len(at_risk),
    }


def _platform_breakdown(platform=DEFAULT_PLATFORM):
    conn = get_db_conn()
    row = conn.execute(
        """
        SELECT
            platform,
            COUNT(*) AS creators,
            COUNT(campaign_label) AS campaign_tagged_creators,
            MAX(last_ingested_at) AS last_ingested_at
        FROM creators
        WHERE platform = ?
        GROUP BY platform
        """,
        (platform,),
    ).fetchone()
    conn.close()
    return dict(row) if row else {
        "platform": platform,
        "creators": 0,
        "campaign_tagged_creators": 0,
        "last_ingested_at": None,
    }


def _trend_rows(platform=DEFAULT_PLATFORM, start=None, end=None):
    video_filters, params = _build_video_filters(start, end)
    where_parts = ["c.platform = ?"]
    all_params = [platform]
    if video_filters:
        where_parts.extend([f"v.{clause}" for clause in video_filters])
        all_params.extend(params)
    query = f"""
    SELECT
        substr(v.published_at, 1, 7) AS month,
        COUNT(v.id) AS videos,
        COALESCE(SUM(v.views), 0) AS total_views,
        COALESCE(SUM(COALESCE(v.likes, 0) + COALESCE(v.comments, 0)), 0) AS engagements
    FROM videos v
    JOIN creators c ON c.id = v.creator_id
    WHERE {' AND '.join(where_parts)}
    GROUP BY substr(v.published_at, 1, 7)
    ORDER BY month ASC
    """
    conn = get_db_conn()
    rows = conn.execute(query, all_params).fetchall()
    conn.close()
    trend = []
    for row in rows:
        total_views = row["total_views"]
        engagement_rate = round((row["engagements"] * 100.0) / total_views, 2) if total_views else 0
        trend.append(
            {
                "month": row["month"],
                "videos": row["videos"],
                "total_views": total_views,
                "engagement_rate": engagement_rate,
            }
        )
    return trend


def ingest_channel(channel_id, platform=DEFAULT_PLATFORM, campaign_label=None, max_results=15):
    if platform != DEFAULT_PLATFORM or not channel_id:
        raise ValueError("provide platform 'youtube' and channel_id")

    video_ids = fetch_channel_videos(channel_id, max_results=max_results)
    stats = fetch_videos_statistics(video_ids) if video_ids else []
    if not stats:
        raise LookupError("no videos returned for channel")

    creator_name = stats[0]["channel_title"] or channel_id
    fetched_at = max((video["fetched_at"] for video in stats), default=None)

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO creators(platform, channel_id, name, source, campaign_label, last_ingested_at)
        VALUES(?, ?, ?, 'youtube_data_api', ?, ?)
        ON CONFLICT(channel_id) DO UPDATE SET
            name = excluded.name,
            campaign_label = COALESCE(excluded.campaign_label, creators.campaign_label),
            last_ingested_at = excluded.last_ingested_at
        """,
        (platform, channel_id, creator_name, campaign_label, fetched_at),
    )
    creator_id = cur.execute(
        "SELECT id FROM creators WHERE channel_id = ?",
        (channel_id,),
    ).fetchone()["id"]

    inserted = 0
    updated = 0
    for video in stats:
        existing = cur.execute(
            "SELECT id FROM videos WHERE video_id = ?",
            (video["video_id"],),
        ).fetchone()
        cur.execute(
            """
            INSERT INTO videos(creator_id, video_id, title, published_at, views, likes, comments, fetched_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                creator_id = excluded.creator_id,
                title = excluded.title,
                published_at = excluded.published_at,
                views = excluded.views,
                likes = excluded.likes,
                comments = excluded.comments,
                fetched_at = excluded.fetched_at
            """,
            (
                creator_id,
                video["video_id"],
                video["title"],
                video["published_at"],
                video["views"],
                video["likes"],
                video["comments"],
                video["fetched_at"],
            ),
        )
        if existing:
            updated += 1
        else:
            inserted += 1
    conn.commit()
    conn.close()
    return {
        "platform": platform,
        "channel_id": channel_id,
        "creator_name": creator_name,
        "campaign_label": campaign_label,
        "fetched": len(stats),
        "inserted": inserted,
        "updated": updated,
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/ingest", methods=["POST"])
def ingest():
    payload = request.get_json() or {}
    platform = payload.get("platform", DEFAULT_PLATFORM)
    channel_id = payload.get("channel_id")
    campaign_label = payload.get("campaign_label")
    max_results = min(max(_parse_int(payload.get("max_results"), 15), 1), 50)
    try:
        result = ingest_channel(
            channel_id=channel_id,
            platform=platform,
            campaign_label=campaign_label,
            max_results=max_results,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": f"ingest failed: {exc}"}), 500
    return jsonify(result)


@app.route("/creators", methods=["GET"])
def creators():
    platform = request.args.get("platform", DEFAULT_PLATFORM)
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    min_views = _parse_int(request.args.get("min_views"), 0)
    limit = min(max(_parse_int(request.args.get("limit"), 100), 1), 500)
    sort_by = request.args.get("sort_by", "total_views")
    sort_dir = request.args.get("sort_dir", "desc")
    try:
        min_engagement = float(request.args.get("min_engagement", 0))
    except (TypeError, ValueError):
        min_engagement = 0.0

    rows = _creator_query_results(
        platform=platform,
        start=start,
        end=end,
        min_views=min_views,
        min_engagement=min_engagement,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
    )
    for row in rows:
        row["alert_status"] = (
            "watch"
            if row["videos"] > 0 and (row["engagement_rate"] < 1.5 or row["avg_views"] < 25000)
            else "healthy"
        )
    return jsonify(rows)


@app.route("/analytics/overview", methods=["GET"])
def analytics_overview():
    platform = request.args.get("platform", DEFAULT_PLATFORM)
    start = request.args.get("start_date")
    end = request.args.get("end_date")
    min_views = _parse_int(request.args.get("min_views"), 0)
    creators = _creator_query_results(
        platform=platform,
        start=start,
        end=end,
        min_views=min_views,
        sort_by="total_views",
        sort_dir="desc",
        limit=500,
    )
    return jsonify(
        {
            "summary": _analytics_overview(creators),
            "platform_breakdown": _platform_breakdown(platform),
            "trend": _trend_rows(platform=platform, start=start, end=end),
        }
    )


@app.route("/analytics/top", methods=["GET"])
def analytics_top():
    platform = request.args.get("platform", DEFAULT_PLATFORM)
    metric = request.args.get("metric", "total_views")
    limit = min(max(_parse_int(request.args.get("limit"), 10), 1), 50)
    rows = _creator_query_results(
        platform=platform,
        sort_by=metric if metric in VALID_SORT_FIELDS else "total_views",
        sort_dir="desc",
        limit=limit,
    )
    return jsonify(
        [
            {
                "name": row["name"],
                "channel_id": row["channel_id"],
                "total_views": row["total_views"],
                "avg_views": row["avg_views"],
                "engagement_rate": row["engagement_rate"],
                "videos": row["videos"],
                "campaign_label": row["campaign_label"],
            }
            for row in rows
        ]
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
