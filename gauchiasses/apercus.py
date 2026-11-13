"""Aperçus des pages (Open Graph) : titre, description et image, gardés en cache."""
from __future__ import annotations

import concurrent.futures as cf
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin

from .config import CACHE_DIR, DELAI_ECHEC
from .reseau import PAGE_BYTES, http_get
from .texte import strip_html

CACHE_APERCUS = CACHE_DIR / "previews_cache.json"

WANTED_META = {"og:title", "og:description", "og:image", "twitter:image", "description"}


class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        a = dict(attrs)
        key = (a.get("property") or a.get("name") or "").lower()
        if key in WANTED_META and a.get("content") and key not in self.meta:
            self.meta[key] = a["content"]


def fetch_preview(link: str) -> dict:
    """Titre, description et image de la page. Dictionnaire vide en cas d'échec."""
    try:
        data, final_url = http_get(link, timeout=10, limit=PAGE_BYTES)
    except Exception:
        return {}
    parser = MetaParser()
    try:
        parser.feed(data.decode("utf-8", errors="replace"))
    except Exception:
        pass
    m = parser.meta
    image = m.get("og:image") or m.get("twitter:image")
    return {
        "title": m.get("og:title", ""),
        "description": strip_html(m.get("og:description") or m.get("description") or "", 220),
        "image": urljoin(final_url, image) if image else "",
    }

# ---------- Cache des aperçus ----------

def lire_cache() -> dict[str, dict]:
    return json.loads(CACHE_APERCUS.read_text(encoding="utf-8")) if CACHE_APERCUS.exists() else {}


def est_echec(entree: dict) -> bool:
    """Page qui n'a jamais pu être lue : entrée vide (ancien format) ou marquée « echec » (date de l'essai)."""
    return not entree or "echec" in entree


def apercus_des_liens(cache: dict[str, dict], links: list[str]) -> dict[str, dict]:
    """Aperçus des liens donnés, en copie (le cache garde les URL d'origine des images).
    Une page en échec donne un aperçu vide."""
    return {l: ({} if est_echec(cache[l]) else dict(cache[l])) for l in links if l in cache}


def load_previews(links: list[str], use_cache: bool = True) -> dict[str, dict]:
    """Aperçus des liens. Une page déjà lue n'est pas relue ; une page en échec est réessayée après DELAI_ECHEC."""
    cache = lire_cache() if use_cache else {}
    maintenant = datetime.now(timezone.utc).timestamp()
    a_lire = [l for l in dict.fromkeys(links)
              if l not in cache or (est_echec(cache[l]) and maintenant - cache[l].get("echec", 0) > DELAI_ECHEC)]
    print(f"[aperçus] {len(a_lire)} page(s) à récupérer, {len(set(links)) - len(a_lire)} en cache")
    if a_lire:
        with cf.ThreadPoolExecutor(max_workers=8) as pool:
            for link, preview in zip(a_lire, pool.map(fetch_preview, a_lire)):
                cache[link] = preview or {"echec": maintenant}

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_APERCUS.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return apercus_des_liens(cache, links)
