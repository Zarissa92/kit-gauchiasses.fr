"""Lecture des fichiers de sources/ : flux RSS, chaînes Twitch, réglages locaux, catégories.

Une ligne « [Nom] » seule ouvre une catégorie ; les flux ou chaînes qui suivent y vont.
Sans catégorie : bloc « Des Liens ».
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

LINE_RE = re.compile(r'^\s*"([^"]+)"\s*(?::\s*\d+)?\s*(?:#.*)?$')  # ": ID" accepté, ignoré
CONFIG_RE = re.compile(r'^\s*(!)?\s*"([^"]+)"\s*(?:\|\s*(.+?))?\s*$')
TWITCH_LINE_RE = re.compile(r'^\s*"([^"]+)"\s*(?::\s*\d+)?\s*(?:#.*)?$')  # ": ID" accepté, ignoré
CATEGORY_RE = re.compile(r'^\s*\[([^\[\]]+)\]\s*$')  # « [Catégorie] » seul sur sa ligne
AUTRES = "Des Liens"  # titre du bloc des sources qui ne sont dans aucune catégorie


def read_feeds(path: Path) -> list[str]:
    """URLs des flux, sans doublons, dans l'ordre du fichier."""
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if CATEGORY_RE.match(line):  # ligne de catégorie : lue par read_categories
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
            print(f"[flux_corrige_main] ligne ignorée (format invalide) : {line}", file=sys.stderr)
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
        if CATEGORY_RE.match(line):  # ligne de catégorie : lue par read_categories
            continue
        m = TWITCH_LINE_RE.match(line)
        if not m:
            print(f"[twitch] ligne ignorée (format invalide) : {line}", file=sys.stderr)
            continue
        name = m.group(1).lower().strip()
        if name not in names:
            names.append(name)
    return names


def read_categories(feeds: Path, twitch: Path) -> dict[str, str]:
    """Catégorie de chaque source. Une ligne « [Nom] » seule ouvre une catégorie ; les sources
    qui suivent y vont, jusqu'à la ligne suivante. Clé : l'URL d'un flux RSS, ou « twitch:nom »."""
    categories: dict[str, str] = {}
    for path, est_twitch in ((feeds, False), (twitch, True)):
        if not path.exists():
            continue
        regex = TWITCH_LINE_RE if est_twitch else LINE_RE
        courante = None
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            titre = CATEGORY_RE.match(line)
            if titre:
                courante = titre.group(1).strip()
                continue
            m = regex.match(line)
            if not m or courante is None:
                continue
            cle = f"twitch:{m.group(1).lower().strip()}" if est_twitch else m.group(1)
            categories.setdefault(cle, courante)  # une source ne garde que sa première catégorie
    return categories


def ordre_des_categories(items: list[dict], categories: dict[str, str]) -> list[str]:
    """Catégories présentes dans les articles : ordre du fichier de flux, « Des Liens » en dernier."""
    presentes = {categories.get(i["key"], AUTRES) for i in items}
    ordre = [c for c in dict.fromkeys(categories.values()) if c in presentes]
    if AUTRES in presentes:
        ordre.append(AUTRES)
    return ordre
