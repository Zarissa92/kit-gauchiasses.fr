#!/usr/bin/env python3
"""Garde des éléments immuables de index.html.

Le bloc entre <!-- IMMUABLE:DEBUT --> et <!-- IMMUABLE:FIN --> (cagnotte, 3 cartes,
lien veille, Discord, code de conduite) ne doit jamais être modifié par un build.

Usage :
    python3 garde_immuable.py enregistrer   # mémorise l'empreinte actuelle (après une modif voulue à la main)
    python3 garde_immuable.py verifier      # échoue (code 1) si le bloc a changé

Un build qui écrit index.html doit appeler verifier_zone() avant d'écrire, et
verifier_zone() sur le résultat avant de l'enregistrer.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent  # bin/
ROOT = HERE.parent
PAGE = ROOT / "index.html"
EMPREINTE = ROOT / "data" / "immuable.json"
DEBUT = "<!-- IMMUABLE:DEBUT"
FIN = "<!-- IMMUABLE:FIN -->"
# Éléments qui doivent être présents dans la zone
ATTENDUS = ['class="cagnotte"', 'class="grille points"', 'class="veille-lien"', "discord.gg", 'id="code-conduite"']


def zone(texte: str) -> str:
    if texte.count(DEBUT) != 1 or texte.count(FIN) != 1:
        raise SystemExit("Marqueurs IMMUABLE absents ou en double dans index.html")
    i = texte.index(DEBUT)
    j = texte.index(FIN) + len(FIN)
    bloc = texte[i:j]
    manquants = [a for a in ATTENDUS if a not in bloc]
    if manquants:
        raise SystemExit(f"Éléments immuables manquants : {manquants}")
    return bloc


def empreinte(texte: str) -> str:
    return hashlib.sha256(zone(texte).encode("utf-8")).hexdigest()


def enregistrer() -> None:
    EMPREINTE.parent.mkdir(parents=True, exist_ok=True)
    EMPREINTE.write_text(json.dumps({"sha256": empreinte(PAGE.read_text(encoding="utf-8"))}, indent=1), encoding="utf-8")
    print("empreinte enregistrée")


def verifier_zone(texte: str) -> None:
    """Lève SystemExit si le bloc immuable ne correspond pas à l'empreinte enregistrée."""
    if not EMPREINTE.exists():
        raise SystemExit("Pas d'empreinte : lance d'abord `garde_immuable.py enregistrer`")
    attendu = json.loads(EMPREINTE.read_text(encoding="utf-8"))["sha256"]
    if empreinte(texte) != attendu:
        raise SystemExit("Le bloc immuable a été modifié : écriture refusée")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "verifier"
    if action == "enregistrer":
        enregistrer()
    elif action == "verifier":
        verifier_zone(PAGE.read_text(encoding="utf-8"))
        print("OK : bloc immuable inchangé")
    else:
        raise SystemExit("Usage : garde_immuable.py enregistrer|verifier")
