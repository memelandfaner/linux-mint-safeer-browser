"""
Safeer Fast YouTube Engine (InnerTube API Resolver)
Extracts YouTube video data directly via InnerTube JSON structures (videoRenderer)
providing ultra-fast, lightweight metadata parsing without heavy browser DOM overhead.
"""

import json
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional


def extract_video_renderers(data: Any) -> List[Dict[str, Any]]:
    """Recursively walks any InnerTube JSON structure to extract all videoRenderer nodes."""
    found = []

    def walk(x):
        if isinstance(x, dict):
            if "videoRenderer" in x and isinstance(x["videoRenderer"], dict):
                found.append(x["videoRenderer"])
            else:
                for y in x.values():
                    walk(y)
        elif isinstance(x, list):
            for y in x:
                walk(y)

    walk(data)
    return found


def _extract_text(obj: Any) -> str:
    """Safely extracts text from YouTube's {simpleText: '...'} or {runs: [{text: '...'}]} format."""
    if not obj or not isinstance(obj, dict):
        return ""
    if "simpleText" in obj and isinstance(obj["simpleText"], str):
        return obj["simpleText"]
    if "runs" in obj and isinstance(obj["runs"], list):
        return "".join(run.get("text", "") for run in obj["runs"] if isinstance(run, dict))
    return ""


def parse_video_renderer(v: Dict[str, Any]) -> Dict[str, Any]:
    """Parses a raw videoRenderer dictionary into a clean, normalized video item."""
    video_id = v.get("videoId", "")

    # Extract title
    title = _extract_text(v.get("title"))

    # Extract channel/owner name
    channel = ""
    for k in ("ownerText", "longBylineText", "shortBylineText"):
        if k in v:
            channel = _extract_text(v[k])
            if channel:
                break

    # Extract duration / length
    length = _extract_text(v.get("lengthText"))

    # Extract views
    views = _extract_text(v.get("viewCountText"))

    # Extract publication time
    published = _extract_text(v.get("publishedTimeText"))

    # Extract best thumbnail
    thumbnail = ""
    thumbs = v.get("thumbnail", {}).get("thumbnails", [])
    if isinstance(thumbs, list) and thumbs:
        thumbnail = thumbs[-1].get("url", "")

    return {
        "video_id": video_id,
        "title": title,
        "channel": channel,
        "duration": length,
        "views": views,
        "published": published,
        "thumbnail": thumbnail,
        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
    }


def search_youtube_fast(query: str, limit: int = 20, timeout: float = 4.0) -> List[Dict[str, Any]]:
    """
    Performs a lightweight InnerTube search request and returns structured video items.
    Executes in tens of milliseconds, bypassing YouTube's heavy ~50MB Polymer web bundle.
    """
    if not query or not query.strip():
        return []

    endpoint = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
    payload = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20240101.00.00",
                "hl": "sl",
                "gl": "SI"
            }
        },
        "query": query.strip()
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "X-YouTube-Client-Name": "1",
            "X-YouTube-Client-Version": "2.20240101.00.00"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            renderers = extract_video_renderers(data)
            results = []
            for r in renderers[:limit]:
                item = parse_video_renderer(r)
                if item["video_id"]:
                    results.append(item)
            return results
    except Exception as e:
        print(f"[YouTube Fast Engine] Napaka pri poizvedbi: {e}")
        return []
