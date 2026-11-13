"""Publication : construit le site puis copie build/ dans la racine servie par nginx (sur le serveur).

build/ contient tout le site et rien d'autre : la page principale, le KiosKe, les flux RSS, les images,
les fichiers statiques. Le code, les données et les fichiers de sources ne sont jamais publiés.

Usage (voir bin/publier_public.py) :
    publier_public.py                 # construit puis copie
    publier_public.py --sans-build    # copie seulement ce qui est déjà dans build/
    publier_public.py --simple        # construit sans réseau (build_site.py --simple), puis copie
    publier_public.py --public DOSSIER  # autre dossier de sortie (défaut : racine_web de gauchiasses.cfg)
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import immuable
from .config import BUILD, DOSSIER_IMAGES, DOSSIER_RSS_CATEGORIES, NOM_ACCUEIL, NOM_VEILLE, RACINE_WEB
from .construction import analyser_arguments, construire, copier_si_change
from .verrou import verrou

# Sans ces fichiers, rien n'est publié.
OBLIGATOIRES = [NOM_ACCUEIL, NOM_VEILLE, "favicon.svg", "preview.png", "apple-touch-icon.png", "rss.xml",
                "fonts/russo-one.woff2"]
# Dossiers entièrement générés : un fichier qui n'est plus dans build/ est retiré de la racine web.
DOSSIERS_PURGES = [DOSSIER_IMAGES, DOSSIER_RSS_CATEGORIES]


def publier(public: Path) -> None:
    page = BUILD / NOM_ACCUEIL
    for nom in OBLIGATOIRES:
        if not (BUILD / nom).exists():
            raise SystemExit(f"Fichier absent, rien publié : build/{nom} (lance d'abord un build complet)")
    # Rien n'est publié si le bloc immuable de la page principale a changé (source et copie de build/).
    immuable.verifier_page(page.read_text(encoding="utf-8"))

    fichiers = [f for f in sorted(BUILD.rglob("*")) if f.is_file() and f.suffix != ".tmp"]
    copies = 0
    for source in fichiers:
        cible = public / source.relative_to(BUILD)
        if copier_si_change(source, cible):
            copies += 1
            print(f"[copie] build/{source.relative_to(BUILD)} -> {cible}", flush=True)

    retires = 0
    for dossier in DOSSIERS_PURGES:
        attendus = {f.name for f in (BUILD / dossier).glob("*")}
        for ancien in (public / dossier).glob("*"):
            if ancien.is_file() and ancien.name not in attendus:
                ancien.unlink()
                retires += 1
    print(f"OK : site publié dans {public} ({copies} fichier(s) copié(s), "
          f"{len(fichiers) - copies} déjà à jour, {retires} retiré(s))", flush=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sans-build", action="store_true", help="ne pas reconstruire : publier build/ tel quel")
    parser.add_argument("--simple", action="store_true", help="reconstruire sans réseau avant de publier")
    parser.add_argument("--public", type=Path, default=RACINE_WEB,
                        help=f"dossier de sortie (défaut : {RACINE_WEB}, racine_web de gauchiasses.cfg)")
    args = parser.parse_args(argv)

    with verrou():  # le build et la copie forment un tout : pas de build concurrent entre les deux
        if not args.sans_build:
            construire(analyser_arguments(["--simple"] if args.simple else []))
        publier(args.public)
