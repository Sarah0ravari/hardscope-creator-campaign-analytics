import sys
from pathlib import Path

import pytest
import werkzeug

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app as app_module


@pytest.fixture()
def client(tmp_path, monkeypatch):
    tmpdb = tmp_path / "test.db"
    monkeypatch.setattr(app_module, "DB_PATH", tmpdb)
    app_module.init_db()
    app_module.app.config["TESTING"] = True
    if not hasattr(werkzeug, "__version__"):
        monkeypatch.setattr(werkzeug, "__version__", "2.3.8", raising=False)
    with app_module.app.test_client() as test_client:
        yield test_client


def test_db_init_creates_tables(tmp_path, monkeypatch):
    tmpdb = tmp_path / "schema.db"
    monkeypatch.setattr(app_module, "DB_PATH", tmpdb)
    app_module.init_db()
    assert tmpdb.exists()
    conn = app_module.get_db_conn()
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    creator_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(creators)").fetchall()
    }
    conn.close()
    assert "creators" in tables
    assert "videos" in tables
    assert {"source", "campaign_label", "last_ingested_at"}.issubset(creator_columns)


def test_ingest_and_creators_analytics(client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "fetch_channel_videos",
        lambda channel_id, max_results=15: ["vid-1", "vid-2"],
    )
    monkeypatch.setattr(
        app_module,
        "fetch_videos_statistics",
        lambda video_ids: [
            {
                "video_id": "vid-1",
                "title": "Launch recap",
                "published_at": "2026-01-10T00:00:00Z",
                "channel_title": "Creator One",
                "views": 120000,
                "likes": 3200,
                "comments": 260,
                "fetched_at": "2026-03-24T00:00:00Z",
            },
            {
                "video_id": "vid-2",
                "title": "Product review",
                "published_at": "2026-02-11T00:00:00Z",
                "channel_title": "Creator One",
                "views": 80000,
                "likes": 1800,
                "comments": 120,
                "fetched_at": "2026-03-24T00:00:00Z",
            },
        ],
    )

    ingest_response = client.post(
        "/ingest",
        json={
            "platform": "youtube",
            "channel_id": "channel-123",
            "campaign_label": "Spring Refresh",
        },
    )
    assert ingest_response.status_code == 200
    payload = ingest_response.get_json()
    assert payload["inserted"] == 2
    assert payload["updated"] == 0

    creators_response = client.get("/creators?min_views=100000")
    assert creators_response.status_code == 200
    creators = creators_response.get_json()
    assert len(creators) == 1
    creator = creators[0]
    assert creator["name"] == "Creator One"
    assert creator["total_views"] == 200000
    assert creator["videos"] == 2
    assert creator["engagement_rate"] == pytest.approx(2.69, rel=1e-2)
    assert creator["alert_status"] == "healthy"

    overview_response = client.get("/analytics/overview")
    assert overview_response.status_code == 200
    overview = overview_response.get_json()
    assert overview["summary"]["total_creators"] == 1
    assert overview["summary"]["total_views"] == 200000
    assert overview["summary"]["top_creator"]["name"] == "Creator One"
    assert overview["platform_breakdown"]["campaign_tagged_creators"] == 1
    assert [row["month"] for row in overview["trend"]] == ["2026-01", "2026-02"]


def test_ingest_returns_503_on_runtime_errors(client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "fetch_channel_videos",
        lambda channel_id, max_results=15: (_ for _ in ()).throw(RuntimeError("YT_API_KEY not set")),
    )
    response = client.post("/ingest", json={"platform": "youtube", "channel_id": "missing-key"})
    assert response.status_code == 503
    assert response.get_json()["error"] == "YT_API_KEY not set"
