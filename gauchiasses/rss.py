"""Flux RSS 2.0 produits par le site : rss.xml (tout) et rss/<catégorie>.xml."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from zoneinfo import ZoneInfo

from .config import NOM_KIOSKE, NOM_VEILLE, RSS_MAX, URL_SITE
from .texte import esc

FUSEAU_PARIS = ZoneInfo("Europe/Paris")


def date_rss(d: datetime) -> str:
    """Date au format RFC 822 (exigé par RSS 2.0), dans l'heure de Paris (CET/CEST)."""
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return format_datetime(d.astimezone(FUSEAU_PARIS))


def render_rss(items: list[dict], titre: str = f"Le {NOM_KIOSKE}", adresse_flux: str = f"{URL_SITE}/rss.xml",
               description: str = "Articles et vidéos des sources suivies, mis à jour automatiquement.") -> str:
    """Flux RSS 2.0 : les RSS_MAX articles les plus récents de la liste donnée."""
    epoque = datetime.min.replace(tzinfo=timezone.utc)
    recents = sorted(items, key=lambda i: i["date"] or epoque, reverse=True)[:RSS_MAX]
    lignes = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        f"<title>{esc(titre)}</title>",
        f"<link>{URL_SITE}/{NOM_VEILLE}</link>",
        f"<description>{esc(description)}</description>",
        "<language>fr-FR</language>",
        f"<lastBuildDate>{date_rss(datetime.now(timezone.utc))}</lastBuildDate>",
        f'<atom:link href="{esc(adresse_flux)}" rel="self" type="application/rss+xml"/>',
    ]
    for it in recents:
        lignes.append("<item>")
        lignes.append(f"<title>{esc(it['source'] + ' : ' + it['title'])}</title>")
        lignes.append(f"<link>{esc(it['link'])}</link>")
        lignes.append(f'<guid isPermaLink="true">{esc(it["link"])}</guid>')
        if it["date"]:
            lignes.append(f"<pubDate>{date_rss(it['date'])}</pubDate>")
        lignes.append(f"<category>{esc(it['source'])}</category>")
        content = it.get("content") or it.get("summary", "")
        if content:
            lignes.append(f"<description>{esc(content)}</description>")
        lignes.append("</item>")
    lignes += ["</channel>", "</rss>"]
    return "\n".join(lignes) + "\n"
