"""Petits outils de texte : échappement HTML, nettoyage, tri et noms de fichiers."""
from __future__ import annotations

import html
import re
import unicodedata

def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def strip_html(text: str, limit: int | None = 280) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if limit is None:
        return text
    return text[:limit] + "…" if len(text) > limit else text


def cle_alphabetique(nom: str) -> str:
    """Clé de tri insensible à la casse et aux accents (« Élan » se range avec « E »)."""
    return unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().casefold()


def slug_categorie(nom: str) -> str:
    """« Médias d'enquête » -> « medias-d-enquete »."""
    texte = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", texte).strip("-") or "categorie"


def slugs_categories(ordre: list[str]) -> dict[str, str]:
    """Nom de fichier de chaque catégorie. Deux catégories au même nom reçoivent un suffixe -2, -3…"""
    slugs: dict[str, str] = {}
    utilises: set[str] = set()
    for c in ordre:
        base = slug_categorie(c)
        s, k = base, 2
        while s in utilises:
            s, k = f"{base}-{k}", k + 1
        utilises.add(s)
        slugs[c] = s
    return slugs
