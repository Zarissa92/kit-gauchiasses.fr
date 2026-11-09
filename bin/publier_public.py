#!/usr/bin/env python3
"""Construit la veille puis copie le site dans public/ (exécuté sur le serveur).

Ce qui est copié dans public/ :
    index.html, favicon.svg          (page principale, vérifiée par le garde immuable)
    veille.html                      (page de veille, à la racine du projet)
    fonts/russo-one.woff2, fonts/OFL.txt   (police locale et sa licence)

Les caches, bin/, data/, deploy/ et les fichiers de flux ne sortent jamais de la racine du projet.

Usage :
    python3 bin/publier_public.py                 # construit puis copie
    python3 bin/publier_public.py --sans-build    # copie seulement ce qui existe déjà
    python3 bin/publier_public.py --public DIR    # autre dossier de sortie (tests)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent     # bin/
ROOT = HERE.parent                         # racine du projet
PUBLIC_DEFAUT = ROOT / "public"
sys.path.insert(0, str(HERE))
import garde_immuable  # noqa: E402  (même dossier bin/)


def construire(args_build: list[str]) -> None:
    cmd = [sys.executable, str(HERE / "build_site.py"), *args_build]
    print("[build] " + " ".join(cmd[1:]), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def copier(source: Path, cible: Path) -> None:
    """Copie atomique : écrit un fichier temporaire puis le renomme."""
    cible.parent.mkdir(parents=True, exist_ok=True)
    tmp = cible.with_name(cible.name + ".tmp")
    shutil.copyfile(source, tmp)
    os.replace(tmp, cible)
    print(f"[copie] {source.relative_to(ROOT)} -> {cible}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sans-build", action="store_true", help="ne pas reconstruire la veille")
    parser.add_argument("--public", type=Path, default=PUBLIC_DEFAUT, help="dossier de sortie (défaut : public/)")
    args = parser.parse_args()

    if not args.sans_build:
        construire([])  # écrit veille.html à la racine

    page = ROOT / "index.html"
    # La page principale n'est publiée que si son bloc immuable est intact.
    garde_immuable.verifier_zone(page.read_text(encoding="utf-8"))

    sources = [
        (page, args.public / "index.html"),
        (ROOT / "favicon.svg", args.public / "favicon.svg"),
        (ROOT / "veille.html", args.public / "veille.html"),
        (ROOT / "fonts" / "russo-one.woff2", args.public / "fonts" / "russo-one.woff2"),
        (ROOT / "fonts" / "OFL.txt", args.public / "fonts" / "OFL.txt"),
    ]
    for source, cible in sources:
        if not source.exists():
            raise SystemExit(f"Fichier absent, rien publié : {source}")
    for source, cible in sources:
        copier(source, cible)
    print("OK : site publié dans", args.public, flush=True)


if __name__ == "__main__":
    main()
