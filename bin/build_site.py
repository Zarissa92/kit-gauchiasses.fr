#!/usr/bin/env python3
"""Génère la page de veille statique (veille.html, à la racine) à partir d'une liste de flux RSS.

Pour chaque article : titre, source, date, description et aperçu
(image Open Graph de la page, à défaut image du flux).

Sources :
    - flux RSS : RSS_feeds.txt, à côté de ce script ;
    - chaînes Twitch : Twich_feeds.txt, à côté de ce script, via yt-dlp.
    Réglages locaux (renommer, ignorer un flux) : flux_perso.txt, à côté de ce script.

Usage :
    python3 build_site.py                          # tous les articles de chaque flux RSS
    python3 build_site.py -rss mes_flux.txt -tw mes_chaines.txt   # autres fichiers d'entrée
    python3 build_site.py --no-twitch              # RSS seulement
    python3 build_site.py --no-previews            # rapide, sans visiter les pages

Dépendances : feedparser et yt-dlp (déjà dans le venv du bot), le reste est en stdlib.
Caches dans data/cache/ : previews_cache.json (aperçus), twitch_cache.json (dates des vidéos).
Supprime un cache pour forcer une nouvelle récupération.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import html
import json
import random
import re
import sqlite3
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
import yt_dlp

HERE = Path(__file__).resolve().parent  # bin/
ROOT = HERE.parent                      # racine du projet
# Listes du bot Discord, lues uniquement en lecture.
DEFAULT_FEEDS = ROOT / "RSS_feeds.txt"
DEFAULT_TWITCH = ROOT / "Twich_feeds.txt"
LOCAL_CONFIG = ROOT / "flux_perso.txt"
OUT_DIR = ROOT  # la page est écrite à la racine du projet
CACHE_DIR = ROOT / "data" / "cache"  # caches du build, non synchronisés
HISTORIQUE_DB = ROOT / "data" / "historique.db"  # tout ce qui a déjà été récupéré (jamais publié)
NOM_PAGE = "veille.html"  # nom du fichier HTML produit à la racine (modifiable avec --nom)

LINE_RE = re.compile(r'^\s*"([^"]+)"\s*(?::\s*\d+)?\s*(?:#.*)?$')  # ": ID" accepté, ignoré
CONFIG_RE = re.compile(r'^\s*(!)?\s*"([^"]+)"\s*(?:\|\s*(.+?))?\s*$')
TWITCH_LINE_RE = re.compile(r'^\s*"([^"]+)"\s*(?::\s*\d+)?\s*(?:#.*)?$')  # ": ID" accepté, ignoré
TWITCH_SCAN = 15  # nb de vidéos regardées par chaîne (un appel de détail par vidéo, donc limité)
UA = "Mozilla/5.0 (compatible; rss-static-site/1.0)"
PAGE_BYTES = 300_000  # on ne lit que le début des pages pour trouver les <meta>
WANTED_META = {"og:title", "og:description", "og:image", "twitter:image", "description"}


# ---------- Lecture des flux ----------

def read_feeds(path: Path) -> list[str]:
    """URLs des flux, sans doublons, dans l'ordre du fichier."""
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = LINE_RE.match(line)
        if not m:
            print(f"[feeds] ligne ignorée (format invalide) : {line}", file=sys.stderr)
            continue
        if m.group(1) not in urls:
            urls.append(m.group(1))
    return urls


def read_local(path: Path) -> tuple[set[str], dict[str, str]]:
    """Réglages locaux : flux ignorés (!"URL") et noms d'affichage ("URL" | Nom)."""
    ignored, names = set(), {}
    if not path.exists():
        return ignored, names
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = CONFIG_RE.match(line)
        if not m:
            print(f"[flux_perso] ligne ignorée (format invalide) : {line}", file=sys.stderr)
            continue
        bang, url, name = m.groups()
        if bang:
            ignored.add(url)
        elif name:
            names[url] = name
    return ignored, names


def read_twitch(path: Path) -> list[str]:
    """Noms des chaînes Twitch, en minuscules, sans doublons."""
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = TWITCH_LINE_RE.match(line)
        if not m:
            print(f"[twitch] ligne ignorée (format invalide) : {line}", file=sys.stderr)
            continue
        name = m.group(1).lower().strip()
        if name not in names:
            names.append(name)
    return names


def http_get(url: str, timeout: int = 15, limit: int | None = None) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(limit) if limit else resp.read()
        return data, resp.geturl()


def strip_html(text: str, limit: int = 280) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + "…" if len(text) > limit else text


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
        items.append({
            "title": entry.get("title") or "Sans titre",
            "link": link,
            "date": datetime(*t[:6], tzinfo=timezone.utc) if t else None,
            "source": source,
            "summary": strip_html(entry.get("summary", "")),
            "image": rss_image(entry),
            "key": url,
        })
    print(f"[flux] {source} : {len(items)} article(s)")
    return items


# ---------- Twitch (yt-dlp) ----------

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
    return [{"id": vid, **video_details(vid)} for vid in ids]


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
            items.append({
                "title": v.get("title") or "Sans titre",
                "link": f"https://www.twitch.tv/videos/{v['id']}",
                "date": date,
                "source": f"Twitch · {name}",
                "summary": f"Durée : {duration}" if duration else "",
                "image": v.get("thumbnail"),
                "kind": "twitch",
                "key": f"twitch:{name}",
            })
        print(f"[twitch] {name} : {len(videos)} vidéo(s)")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return items


# ---------- Aperçus (Open Graph) ----------

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


def load_previews(links: list[str], use_cache: bool = True) -> dict[str, dict]:
    cache_file = CACHE_DIR / "previews_cache.json"
    cache = {}
    if use_cache and cache_file.exists():
        cache = json.loads(cache_file.read_text(encoding="utf-8"))

    missing = [l for l in links if l not in cache]
    print(f"[aperçus] {len(missing)} page(s) à récupérer, {len(links) - len(missing)} en cache")
    if missing:
        with cf.ThreadPoolExecutor(max_workers=8) as pool:
            for link, preview in zip(missing, pool.map(fetch_preview, missing)):
                cache[link] = preview

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return cache


# ---------- HTML (style de gauchiasses.fr : noir, rouge, pluie CSS, sans JavaScript) ----------

CSS = """
/* Police uniforme du site : fichier local, servi depuis fonts/ (une copie à la racine publiée) */
@font-face {
  font-family: "Russo One";
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url("../fonts/russo-one.woff2") format("woff2");
}
html, body, body * { font-family: "Russo One", "Courier New", monospace !important; }
:root {
  --red: #ffffff;
  --red-dim: #ffffff;
  --red-light: #ffffff;
  --bg: #000;
  --panel: #0a0000;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

html, body {
  min-height: 100%;
  background: var(--bg);
  color: var(--red);
  font-family: "Courier New", Courier, monospace;
  overflow-x: hidden;
  overflow-y: auto;
}

.panel {
  position: relative;
  z-index: 1;
  max-width: 560px;
  width: calc(100% - 32px);
  margin: 2rem auto 1.5rem;
  padding: 2.5rem 2rem;
  background: var(--panel);
  border: 1px solid var(--red-dim);
  box-shadow: 0 0 30px rgba(255, 255, 255, 0.35), inset 0 0 20px rgba(255, 255, 255, 0.1);
  text-align: center;
}
.kicker { font-size: 0.85rem; color: var(--red-light); opacity: 0.8; margin-bottom: 1rem; letter-spacing: 0.1em; }
h1 { font-size: clamp(1.8rem, 6vw, 2.8rem); line-height: 1.2; margin-bottom: 1.5rem; text-transform: uppercase; }
.glow {
  color: #fff;
  text-shadow: 0 0 5px var(--red), 0 0 15px var(--red), 0 0 35px var(--red);
  animation: flicker 4s infinite;
}
.cursor { font-size: 1.8rem; line-height: 1; animation: blink 1s steps(1) infinite; }
/* drapeaux trans de chaque côté du titre (comme sur gauchiasses.fr) */
.titre-ligne { display: flex; justify-content: center; align-items: center; gap: .3em; white-space: nowrap; }
.drapeau { font-size: .5em; line-height: 1; }
@media (max-width: 360px) { .titre-ligne { flex-wrap: wrap; white-space: normal; } }
.sub { color: var(--red-light); margin-bottom: 1.2rem; }
.sub-petit { font-size: .8rem; opacity: .7; }


@keyframes blink { 50% { opacity: 0; } }
@keyframes flicker { 0%, 92%, 100% { opacity: 1; } 93% { opacity: 0.4; } 95% { opacity: 1; } 96% { opacity: 0.6; } }
@media (max-width: 480px) { .panel { padding: 2rem 1.2rem; } }

/* pluie rouge en CSS pur */
#pluie { position: fixed; inset: 0; z-index: 0; overflow: hidden; pointer-events: none; }
#pluie i {
  position: absolute; top: 0;
  font: normal 16px/1.15 monospace; white-space: pre; text-align: center;
  color: transparent;
  background: linear-gradient(to top, #ffd0d0 0, #ff1a1a 6%, rgba(255, 26, 26, .55) 45%, transparent 100%);
  -webkit-background-clip: text; background-clip: text;
  transform: translateY(-100%);
  animation-name: chute; animation-timing-function: linear; animation-iteration-count: infinite;
  will-change: transform;
}
@keyframes chute { from { transform: translateY(-100%); } to { transform: translateY(100vh); } }
@media (prefers-reduced-motion: reduce) { #pluie i { animation: none; transform: translateY(20vh); } }

/* sources : une case par source ; le clic ouvre ses articles dans un panneau (popover, sans JavaScript) */
.cartes { position: relative; z-index: 1; max-width: 1200px; width: calc(100% - 32px); margin: 0 auto 2rem; }
.grille { --colonnes: 4; display: grid; grid-template-columns: repeat(var(--colonnes), minmax(0, 1fr)); gap: 1rem; }
@media (max-width: 960px) { .grille { --colonnes: 3; } }
@media (max-width: 640px) { .grille { --colonnes: 2; gap: .6rem; } }

.categorie-titre { display: flex; align-items: center; gap: .5rem; width: 100%; margin: 0 0 .8rem;
  padding: .6rem .9rem; font: inherit; font-size: 1rem; font-weight: 700; text-align: left; text-transform: uppercase;
  background: var(--panel); color: #fff; border: 1px solid var(--red-dim);
  box-shadow: 0 0 12px rgba(255, 255, 255, .25), inset 0 0 14px rgba(255, 255, 255, .08);
  cursor: pointer; }
.categorie-titre::after { content: "▸"; margin-left: auto; transition: transform .2s; }
.categorie-titre:hover, .categorie-titre:focus-visible { color: var(--red-light); outline: none; box-shadow: 0 0 22px var(--red); }

.categorie-panneau { position: fixed; inset: 0; margin: auto;
  width: min(1100px, calc(100vw - 2rem)); height: fit-content; max-height: calc(100vh - 2rem);
  overflow: auto; padding: 2.2rem 1.4rem 1.4rem; box-sizing: border-box;
  background: #0a0000; color: var(--red-light); border: 1px solid var(--red);
  box-shadow: 0 0 30px rgba(255, 255, 255, .5), inset 0 0 20px rgba(255, 255, 255, .1); }
.categorie-panneau::backdrop { background: rgba(0, 0, 0, .8); }
.categorie-panneau h2 { font-size: clamp(1.1rem, 2.6vw, 1.5rem); text-transform: uppercase; color: #fff; margin: 0 2.4rem 1rem 0; }
.categorie-fermer { position: absolute; top: .5rem; right: .5rem; width: 2rem; height: 2rem; border: 1px solid var(--red-dim); background: #000; color: var(--red); font: inherit; font-size: 1.2rem; cursor: pointer; }
.categorie-fermer:hover, .categorie-fermer:focus-visible { background: var(--red); color: #000; }
.compte { font-weight: 400; opacity: .7; font-size: .8rem; }

.carte {
  position: relative; display: flex; flex-direction: column;
  aspect-ratio: 3 / 4; overflow: hidden; text-align: left;
  color: inherit; text-decoration: none;
  background: rgba(8, 0, 0, .92);
  border: 1px solid var(--red-dim);
  box-shadow: 0 0 12px rgba(255, 255, 255, .25), inset 0 0 14px rgba(255, 255, 255, .08);
  transition: border-color .2s, box-shadow .2s, transform .2s;
}
.carte:hover, .carte:focus-visible { border-color: var(--red); box-shadow: 0 0 22px var(--red); transform: translateY(-2px); outline: none; }
.carte-image {
  flex: 0 0 55%; display: flex; align-items: center; justify-content: center; overflow: hidden;
  border-bottom: 1px solid var(--red-dim); background: #140000;
}
.carte-image img { width: 100%; height: 100%; object-fit: cover; object-position: center 25%; display: block; }
.carte-image .lettre {
  font: 700 clamp(3rem, 9vw, 5.5rem) "Courier New", monospace; color: #fff;
  text-shadow: 0 0 6px var(--red), 0 0 22px var(--red);
}
.carte-corps { flex: 1; min-height: 0; overflow: hidden; padding: .6rem .7rem 2.4rem; display: block; }
.carte .meta { font-size: .65rem; color: var(--red-light); opacity: .8; margin-bottom: .3rem; }
.carte h3 { font-size: .82rem; line-height: 1.2; text-transform: uppercase; margin-bottom: .3rem; color: #fff; overflow-wrap: anywhere; }
.carte p { font-size: .72rem; line-height: 1.35; color: var(--red-light); overflow-wrap: anywhere; }
.carte-plus {
  position: absolute; right: .45rem; bottom: .45rem; width: 1.8rem; height: 1.8rem;
  display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--red); background: #000; color: var(--red); font-size: 1.1rem; transition: all .2s;
}
.carte:hover .carte-plus, .carte:focus-visible .carte-plus { background: var(--red); color: #000; box-shadow: 0 0 14px var(--red); }

.mentions { position: relative; z-index: 1; max-width: 1200px; width: calc(100% - 32px); margin: 0 auto 2rem; font-size: .75rem; opacity: .7; text-align: center; }
.mentions a { color: var(--red-light); }
/* ----- nuage des sources (même principe que la page principale) ----- */
:root { --rouge: #ff1a1a; --periode: 5s; }
.nuage { display: flex; flex-wrap: wrap; justify-content: center; gap: .4rem; margin: 1.2rem 0 0; padding: .7rem;
  background: #0a0000; border: 1px solid #fff; box-shadow: 0 0 18px rgba(255, 255, 255, .25); }
.nuage .tag { display: inline-flex; align-items: center; gap: .35rem; padding: .2rem .55rem; border: 1px solid #fff;
  border-radius: .3rem; background: none; color: #fff; font: inherit; font-size: .8rem; line-height: 1.4;
  text-shadow: 0 0 6px #fff; white-space: nowrap; cursor: pointer; animation: tagRouge var(--periode) linear infinite; }
.nuage .tag .nb { font-size: .72rem; opacity: .75; text-shadow: none; }
.nuage .tag:hover, .nuage .tag:focus-visible { color: #000; background: #fff; text-shadow: none; outline: none; }
@keyframes tagRouge { 0%, 100% { color: #fff; border-color: #fff; text-shadow: 0 0 6px #fff; }
  3%, 12% { color: var(--rouge); border-color: var(--rouge); text-shadow: 0 0 6px var(--rouge); }
  15% { color: #fff; border-color: #fff; text-shadow: 0 0 6px #fff; } }
@media (prefers-reduced-motion: reduce) { .nuage .tag { animation: none; } }
"""


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def rain(seed: int = 42, colonnes: int = 40) -> str:
    """Colonnes de pluie rouge, générées une fois (page statique, même rendu à chaque build)."""
    rnd = random.Random(seed)
    chars = "アイウエオカキクケコサシスセソタチツテトナニヌネノ0123456789ABCDEFXYZ*+-=<>"
    parts = []
    for k in range(colonnes):
        left = round(k * 100 / colonnes + rnd.uniform(-0.8, 0.8), 2)
        duree = round(rnd.uniform(6, 16), 1)
        retard = round(-rnd.uniform(0, 16), 1)
        texte = "\n".join(rnd.choice(chars) for _ in range(rnd.randint(14, 30)))
        parts.append(f'<i style="left:{left}%;animation-duration:{duree}s;animation-delay:{retard}s">{esc(texte)}</i>')
    return '<div id="pluie" aria-hidden="true">' + "".join(parts) + "</div>"


def render_card(item: dict, preview: dict) -> str:
    title = preview.get("title") or item["title"]
    summary = item["summary"] or preview.get("description", "")
    image = preview.get("image") or item["image"] or ""
    date = item["date"]
    host = urlparse(item["link"]).netloc.removeprefix("www.")

    if image:
        media = f'<img src="{esc(image)}" alt="" loading="lazy" referrerpolicy="no-referrer">'
    else:
        media = f'<span class="lettre">{esc((item["source"][:1] or "•").upper())}</span>'
    date_html = f'<time datetime="{date.isoformat()}">{date:%d/%m/%Y}</time> · ' if date else ""

    return (
        f'<a class="carte" href="{esc(item["link"])}" target="_blank" rel="noopener noreferrer">'
        f'<div class="carte-image" aria-hidden="true">{media}</div>'
        f'<div class="carte-corps"><p class="meta">{date_html}{esc(host)}</p>'
        f'<h3>{esc(title)}</h3><p>{esc(summary)}</p></div>'
        f'<span class="carte-plus" aria-hidden="true">+</span></a>'
    )


def cle_alphabetique(nom: str) -> str:
    """Clé de tri insensible à la casse et aux accents (« Élan » se range avec « E »)."""
    return unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().casefold()


def render_page(items: list[dict], previews: dict[str, dict], nom_page: str = NOM_PAGE) -> str:
    # Regroupement par source ; sources dans l'ordre alphabétique, articles les plus récents d'abord.
    epoque = datetime.min.replace(tzinfo=timezone.utc)
    items.sort(key=lambda i: i["date"] or epoque, reverse=True)
    groupes: dict[str, list[dict]] = {}
    for item in items:
        groupes.setdefault(item["source"], []).append(item)
    ordre = sorted(groupes, key=cle_alphabetique)

    tags = []
    fenetres = []
    for n, source in enumerate(ordre):
        cartes = "".join(render_card(i, previews.get(i["link"], {})) for i in groupes[source])
        nb = len(groupes[source])
        decalage = (n * 0.618) % 1  # répartit les passages au rouge dans la période
        tags.append(
            f'<button type="button" class="tag" popovertarget="cat-{n}" '
            f'style="animation-delay:calc(var(--periode) * -{decalage:.3f})">'
            f'{esc(source)} <span class="nb">×{nb}</span></button>'
        )
        fenetres.append(
            f'<div id="cat-{n}" class="categorie-panneau" popover>'
            f'<button type="button" class="categorie-fermer" popovertarget="cat-{n}" popovertargetaction="hide" aria-label="Fermer">×</button>'
            f'<h2>{esc(source)} <span class="compte">({nb})</span></h2>'
            f'<div class="grille">{cartes}</div></div>'
        )

    generated = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kiosque</title>
<meta name="description" content="Kiosque : articles et vidéos des sources suivies, mis à jour automatiquement.">
<meta name="theme-color" content="#000000">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<style>{CSS}</style>
</head>
<body>
{rain()}
<main class="panel">
  <p class="kicker">// kiosque automatique ✨</p>
  <h1><span class="titre-ligne"><span class="drapeau" aria-hidden="true">🏳️‍⚧️</span><span class="glow">Le Kiosque</span><span class="drapeau" aria-hidden="true">🏳️‍⚧️</span><span class="cursor" aria-hidden="true">▌</span></span></h1>
  <p class="sub">{len(items)} éléments · {len(groupes)} sources</p>
  <p class="sub-petit">Mis à jour le {generated}</p>
  <div class="nuage" aria-label="Sources">{"".join(tags)}</div>
</main>
<section class="cartes" aria-label="Fenêtres des sources">
{"".join(fenetres)}
</section>
<p class="mentions">Chaque carte renvoie vers la source d'origine. Textes, images et vidéos : leurs auteurs et sites respectifs.</p>
</body>
</html>
"""


# ---------- Historique (SQLite) ----------

class Historique:
    """Tous les articles déjà récupérés. Rien n'est effacé automatiquement :
    la page n'affiche que les sources encore listées (voir charger)."""

    def __init__(self, chemin: Path):
        chemin.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(chemin)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id          TEXT PRIMARY KEY,
                source_key  TEXT NOT NULL,
                source      TEXT,
                title       TEXT,
                link        TEXT NOT NULL,
                date        TEXT,
                summary     TEXT,
                image       TEXT,
                kind        TEXT,
                premier_vu  TEXT NOT NULL,
                dernier_vu  TEXT NOT NULL
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON articles(source_key)")

    def enregistrer(self, items: list[dict]) -> int:
        """Ajoute les nouveaux articles, met à jour les anciens. Retourne le nombre d'articles traités."""
        maintenant = datetime.now(timezone.utc).isoformat()
        with self.conn:
            for it in items:
                date = it["date"].isoformat() if it["date"] else None
                self.conn.execute(
                    """
                    INSERT INTO articles (id, source_key, source, title, link, date, summary, image, kind, premier_vu, dernier_vu)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        source     = excluded.source,
                        title      = excluded.title,
                        date       = COALESCE(excluded.date, articles.date),
                        summary    = excluded.summary,
                        image      = COALESCE(excluded.image, articles.image),
                        dernier_vu = excluded.dernier_vu
                    """,
                    (f"{it['key']}|{it['link']}", it["key"], it["source"], it["title"], it["link"],
                     date, it["summary"], it["image"], it.get("kind", "rss"), maintenant, maintenant),
                )
        return len(items)

    def charger(self, sources: set[str]) -> list[dict]:
        """Articles des sources données uniquement ; les autres restent en base, hors de la page."""
        if not sources:
            return []
        marques = ",".join("?" * len(sources))
        rows = self.conn.execute(
            f"SELECT source_key, source, title, link, date, summary, image, kind "
            f"FROM articles WHERE source_key IN ({marques})",
            tuple(sources),
        ).fetchall()
        return [
            {
                "key": key, "source": source, "title": title, "link": link,
                "date": datetime.fromisoformat(date) if date else None,
                "summary": summary or "", "image": image, "kind": kind,
            }
            for key, source, title, link, date, summary, image, kind in rows
        ]

    def fermer(self) -> None:
        self.conn.close()


# ---------- Programme principal ----------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-rss", dest="rss", type=Path, default=DEFAULT_FEEDS, metavar="FICHIER",
                        help="fichier des flux RSS (défaut : RSS_feeds.txt à côté du script)")
    parser.add_argument("-tw", dest="tw", type=Path, default=DEFAULT_TWITCH, metavar="FICHIER",
                        help="fichier des chaînes Twitch (défaut : Twich_feeds.txt à côté du script)")
    parser.add_argument("--local", type=Path, default=LOCAL_CONFIG, help="réglages locaux (défaut : flux_perso.txt)")
    parser.add_argument("--no-twitch", action="store_true", help="ne pas inclure les chaînes Twitch")
    parser.add_argument("--no-previews", action="store_true", help="ne pas visiter les pages pour les aperçus")
    parser.add_argument("--no-cache", action="store_true", help="ignorer les caches (aperçus et Twitch)")
    parser.add_argument("--nom", default=NOM_PAGE, help="nom du fichier HTML produit (défaut : veille.html)")
    args = parser.parse_args()

    ignored, names = read_local(args.local)
    urls = [u for u in read_feeds(args.rss) if u not in ignored]
    print(f"{len(urls)} flux RSS dans {args.rss.name} ({len(ignored)} ignoré(s) localement)")

    items = []
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for feed_items in pool.map(lambda u: load_feed(u, names), urls):
            items.extend(feed_items)

    if not args.no_twitch:
        channels = read_twitch(args.tw)
        print(f"{len(channels)} chaîne(s) Twitch")
        items.extend(load_twitch(channels, TWITCH_SCAN, use_cache=not args.no_cache))

    # Historique : on enregistre ce qui vient d'être récupéré, puis on affiche
    # les articles des sources encore listées (les autres restent en base).
    sources_actives = set(urls) | {f"twitch:{n}" for n in read_twitch(args.tw)}
    historique = Historique(HISTORIQUE_DB)
    historique.enregistrer(items)
    items = historique.charger(sources_actives)
    historique.fermer()
    print(f"historique : {len(items)} article(s) affiché(s) pour {len(sources_actives)} source(s) active(s)")

    previews = {}
    if not args.no_previews:
        links = [i["link"] for i in items if i.get("kind") != "twitch"]
        previews = load_previews(links, use_cache=not args.no_cache)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sortie = OUT_DIR / args.nom
    sortie.write_text(render_page(items, previews, args.nom), encoding="utf-8")
    print(f"OK : {len(items)} article(s) écrits dans {sortie}")


if __name__ == "__main__":
    main()
