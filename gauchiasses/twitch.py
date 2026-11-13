"""Vidéos des chaînes Twitch (yt-dlp). Les dates et durées déjà connues restent en cache."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import yt_dlp

from .config import CACHE_DIR

def format_duration(seconds) -> str | None:
    if not seconds:
        return None
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    return f"{h}h{m:02d}" if h else f"{m}min{s:02d}"


def twitch_thumb(url: str | None) -> str | None:
    if not url:
        return None
    return (url.replace("%{width}", "640").replace("%{height}", "360")
               .replace("{width}", "640").replace("{height}", "360"))


def video_details(video_id: str) -> dict:
    """Date, durée et miniature d'une vidéo (extraction complète, plus lente)."""
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://www.twitch.tv/videos/{video_id}", download=False) or {}
    return {
        "title": info.get("title") or "",
        "timestamp": info.get("timestamp"),
        "duration": info.get("duration"),
        "thumbnail": twitch_thumb(info.get("thumbnail")),
    }


def fetch_channel_videos(name: str, limit: int) -> list[dict]:
    """Vidéos récentes d'une chaîne (liste rapide, puis détails pour chaque vidéo)."""
    url = f"https://www.twitch.tv/{name}/videos?filter=all&sort=time"
    opts = {
        "extract_flat": "in_playlist",
        "playlistend": limit,
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False) or {}
    ids = []
    for e in info.get("entries") or []:
        vid = str((e or {}).get("id") or "").lstrip("v")
        if vid.isdigit():
            ids.append(vid)
    videos = []
    for vid in ids:
        try:
            videos.append({"id": vid, **video_details(vid)})
        except Exception as exc:  # vidéo invalide (abonnés, supprimée…) : on passe à la suivante
            print(f"[twitch] {name} : vidéo {vid} ignorée : {exc}", file=sys.stderr)
    return videos


def load_twitch(names: list[str], limit: int, use_cache: bool = True) -> list[dict]:
    cache_file = CACHE_DIR / "twitch_cache.json"
    cache = {}
    if use_cache and cache_file.exists():
        cache = json.loads(cache_file.read_text(encoding="utf-8"))

    items = []
    for name in names:
        try:
            videos = fetch_channel_videos(name, limit)
        except Exception as exc:
            print(f"[twitch] {name} : {exc}", file=sys.stderr)
            continue
        for v in videos:
            # Les dates et durées ne changent pas : on garde ce qui est déjà connu.
            if v["id"] in cache:
                v = {"id": v["id"], **cache[v["id"]]}
            else:
                cache[v["id"]] = {k: v[k] for k in ("title", "timestamp", "duration", "thumbnail")}
            date = datetime.fromtimestamp(v["timestamp"], timezone.utc) if v.get("timestamp") else None
            duration = format_duration(v.get("duration"))
            summary_text = f"Durée : {duration}" if duration else ""
            items.append({
                "title": v.get("title") or "Sans titre",
                "link": f"https://www.twitch.tv/videos/{v['id']}",
                "date": date,
                "source": f"Twitch · {name}",
                "summary": summary_text,
                "content": summary_text,
                "image": v.get("thumbnail"),
                "kind": "twitch",
                "key": f"twitch:{name}",
            })
        print(f"[twitch] {name} : {len(videos)} vidéo(s)")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return items
