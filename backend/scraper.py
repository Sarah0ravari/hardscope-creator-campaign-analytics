"""Utilities to fetch videos and statistics using YouTube Data API v3.

Requires environment variable `YT_API_KEY`.
"""
import os
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

YT_API_KEY = os.getenv("YT_API_KEY")
BASE_SEARCH = "https://www.googleapis.com/youtube/v3/search"
BASE_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"


def _requests_session_with_retries(total=3, backoff_factor=1):
    session = requests.Session()
    retries = Retry(
        total=total,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_channel_videos(channel_id, max_results=10):
    """Return list of video IDs for a channel (most recent).

    Implements retries and backoff for transient errors and rate limits.
    """
    if not YT_API_KEY:
        raise RuntimeError("YT_API_KEY not set")
    params = {
        "key": YT_API_KEY,
        "channelId": channel_id,
        "part": "id",
        "order": "date",
        "maxResults": max_results,
        "type": "video",
    }
    session = _requests_session_with_retries()
    r = session.get(BASE_SEARCH, params=params, timeout=10)
    if r.status_code == 429:
        raise RuntimeError("Rate limited by YouTube API (429)")
    r.raise_for_status()
    items = r.json().get("items", [])
    return [it["id"]["videoId"] for it in items if it.get("id", {}).get("videoId")]


def fetch_videos_statistics(video_ids):
    """Return list of video metadata+stats for given IDs.

    Uses a retrying session and tolerates missing counts gracefully.
    """
    if not YT_API_KEY:
        raise RuntimeError("YT_API_KEY not set")
    if not video_ids:
        return []
    params = {
        "key": YT_API_KEY,
        "id": ",".join(video_ids),
        "part": "snippet,statistics",
        "maxResults": len(video_ids),
    }
    session = _requests_session_with_retries()
    r = session.get(BASE_VIDEOS, params=params, timeout=10)
    if r.status_code == 429:
        raise RuntimeError("Rate limited by YouTube API (429)")
    r.raise_for_status()
    out = []
    for item in r.json().get("items", []):
        snip = item.get("snippet", {})
        stats = item.get("statistics", {})
        try:
            views = int(stats.get("viewCount", 0))
        except Exception:
            views = 0
        try:
            likes = int(stats.get("likeCount")) if stats.get("likeCount") else None
        except Exception:
            likes = None
        try:
            comments = int(stats.get("commentCount")) if stats.get("commentCount") else None
        except Exception:
            comments = None
        out.append({
            "video_id": item.get("id"),
            "title": snip.get("title"),
            "published_at": snip.get("publishedAt"),
            "channel_title": snip.get("channelTitle"),
            "views": views,
            "likes": likes,
            "comments": comments,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        })
    return out
