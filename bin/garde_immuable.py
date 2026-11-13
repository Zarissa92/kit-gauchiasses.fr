#!/usr/bin/env python3
"""Garde du bloc immuable (dans accueil/index.html). Voir gauchiasses/immuable.py.

    venv_blog/bin/python bin/garde_immuable.py verifier      # échoue (code 1) si le bloc a changé
    venv_blog/bin/python bin/garde_immuable.py enregistrer   # accepte la version actuelle (après une modif voulue)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # racine du projet : paquet gauchiasses/

from gauchiasses.immuable import main  # noqa: E402

if __name__ == "__main__":
    main(sys.argv[1:])
