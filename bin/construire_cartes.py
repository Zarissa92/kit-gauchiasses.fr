#!/usr/bin/env python3
"""Construit les cartes de la page principale (accueil/index.html). Voir gauchiasses/cartes.py.
Tourne sur le PC, jamais sur le serveur.

    venv_blog/bin/python bin/construire_cartes.py               # toutes les listes de listes/*.txt
    venv_blog/bin/python bin/construire_cartes.py --hors-ligne  # sans interroger Wikipédia (caches seulement)
    venv_blog/bin/python bin/construire_cartes.py --help
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # racine du projet : paquet gauchiasses/

from gauchiasses.cartes import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
