"""Garde du bloc immuable de la page principale.

Le bloc entre <!-- IMMUABLE:DEBUT --> et <!-- IMMUABLE:FIN --> (cagnotte, 3 cartes, lien vers le
KiosKe, lien Discord, code de conduite) est écrit à la main dans accueil/index.html. Aucun build
ne le modifie : la page est recopiée telle quelle dans build/.

Deux contrôles :
- verifier_zone() : le bloc d'un texte correspond à l'empreinte enregistrée (data/immuable.json) ;
- verifier_page() : une page générée ou publiée contient le bloc de la source, à l'identique.
"""
from __future__ import annotations

import hashlib
import json

from .config import EMPREINTE
from .config import PAGE_ACCUEIL as SOURCE

DEBUT = "<!-- IMMUABLE:DEBUT"
FIN = "<!-- IMMUABLE:FIN -->"
# Éléments qui doivent être présents dans la zone
ATTENDUS = ['class="cagnotte"', 'class="grille points"', 'class="veille-lien"', "discord.gg", 'id="code-conduite"']


def zone(texte: str) -> str:
    if texte.count(DEBUT) != 1 or texte.count(FIN) != 1:
        raise SystemExit("Marqueurs IMMUABLE absents ou en double")
    i = texte.index(DEBUT)
    j = texte.index(FIN) + len(FIN)
    bloc = texte[i:j]
    manquants = [a for a in ATTENDUS if a not in bloc]
    if manquants:
        raise SystemExit(f"Éléments immuables manquants : {manquants}")
    return bloc


def empreinte(texte: str) -> str:
    return hashlib.sha256(zone(texte).encode("utf-8")).hexdigest()


def lire_source() -> str:
    if not SOURCE.exists():
        raise SystemExit(f"page principale introuvable : {SOURCE}")
    return SOURCE.read_text(encoding="utf-8")


def enregistrer() -> None:
    EMPREINTE.parent.mkdir(parents=True, exist_ok=True)
    EMPREINTE.write_text(json.dumps({"sha256": empreinte(lire_source())}, indent=1), encoding="utf-8")
    print("empreinte enregistrée")


def verifier_zone(texte: str) -> None:
    """Lève SystemExit si le bloc immuable du texte ne correspond pas à l'empreinte enregistrée."""
    if not EMPREINTE.exists():
        raise SystemExit("Pas d'empreinte : lance d'abord `bin/garde_immuable.py enregistrer`")
    attendu = json.loads(EMPREINTE.read_text(encoding="utf-8"))["sha256"]
    if empreinte(texte) != attendu:
        raise SystemExit("Le bloc immuable a été modifié : écriture refusée")


def verifier_page(page: str) -> None:
    """Contrôle une page générée ou publiée : son bloc immuable correspond à l'empreinte, et il est
    celui de la source, caractère pour caractère."""
    verifier_zone(page)
    source = lire_source()
    verifier_zone(source)
    if zone(page) != zone(source):
        raise SystemExit("Bloc immuable différent de celui de accueil/index.html : écriture refusée")


def main(argv: list[str]) -> None:
    action = argv[0] if argv else "verifier"
    if action == "enregistrer":
        enregistrer()
    elif action == "verifier":
        verifier_zone(lire_source())
        print("OK : bloc immuable inchangé")
    else:
        raise SystemExit("Usage : garde_immuable.py enregistrer|verifier")
