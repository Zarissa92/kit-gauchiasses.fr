"""Récupération des flux RSS (feedparser)."""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import feedparser

from .reseau import http_get
from .texte import strip_html

def rss_image(entry) -> str | None:
    """Image fournie directement par le flux (media:thumbnail, media:content, enclosure)."""
    for m in entry.get("media_thumbnail") or []:
        if m.get("url"):
            return m["url"]
    for m in entry.get("media_content") or []:
        if m.get("url") and (m.get("medium") == "image" or (m.get("type") or "").startswith("image/")):
            return m["url"]
    for link in entry.get("links") or []:
        if link.get("rel") == "enclosure" and (link.get("type") or "").startswith("image/"):
            return link.get("href")
    return None


def load_feed(url: str, names: dict[str, str]) -> list[dict]:
    try:
        data, _ = http_get(url)
    except Exception as exc:  # réseau, timeout, HTTP 4xx/5xx
        print(f"[flux] {url} : {exc}", file=sys.stderr)
        return []

    parsed = feedparser.parse(data)
    source = names.get(url) or parsed.feed.get("title", url)
    items = []
    for entry in parsed.entries:
        link = entry.get("link")
        if not link:
            continue
        t = entry.get("published_parsed") or entry.get("updated_parsed")
        summary_html = entry.get("summary", "")
        items.append({
            "title": entry.get("title") or "Sans titre",
            "link": link,
            "date": datetime(*t[:6], tzinfo=timezone.utc) if t else None,
            "source": source,
            "summary": strip_html(summary_html, limit=280),
            "content": strip_html(summary_html, limit=None),
            "image": rss_image(entry),
            "key": url,
        })
    print(f"[flux] {source} : {len(items)} article(s)")
    return items
