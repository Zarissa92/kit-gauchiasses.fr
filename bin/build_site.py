#!/usr/bin/env python3
"""Construit le site dans build/ (page principale, KiosKe, flux RSS, images). Voir gauchiasses/construction.py.

    venv_blog/bin/python bin/build_site.py            # build complet
    venv_blog/bin/python bin/build_site.py --simple   # pages seules, sans réseau
    venv_blog/bin/python bin/build_site.py --help
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # racine du projet : paquet gauchiasses/

from gauchiasses.construction import main  # noqa: E402

if __name__ == "__main__":
    main()
