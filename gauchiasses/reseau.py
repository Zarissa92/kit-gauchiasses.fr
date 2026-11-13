"""Accès HTTP commun à la veille."""
from __future__ import annotations

import urllib.request

UA = "Mozilla/5.0 (compatible; rss-static-site/1.0)"
PAGE_BYTES = 300_000  # on ne lit que le début des pages pour trouver les <meta>


def http_get(url: str, timeout: int = 15, limit: int | None = None) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(limit) if limit else resp.read()
        return data, resp.geturl()
