#!/usr/bin/env python3
"""Construit le site puis le copie dans la racine servie par nginx. Voir gauchiasses/publication.py.

    venv/bin/python bin/publier_public.py                # construit puis copie (ce que lance le timer)
    venv/bin/python bin/publier_public.py --simple       # construit sans réseau, puis copie
    venv/bin/python bin/publier_public.py --sans-build   # copie build/ tel quel
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # racine du projet : paquet gauchiasses/

from gauchiasses.publication import main  # noqa: E402

if __name__ == "__main__":
    main()
