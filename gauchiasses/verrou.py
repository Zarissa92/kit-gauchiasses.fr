"""Verrou du build : un seul build ou une seule publication à la fois (timer et lancement manuel)."""
from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager

from .config import DATA, VERROU

_tenu = False  # le verrou est déjà pris par ce processus (la publication appelle le build)


@contextmanager
def verrou():
    """Attend la fin d'un autre build en cours, puis garde le verrou jusqu'à la sortie du bloc."""
    global _tenu
    if _tenu:
        yield
        return
    DATA.mkdir(parents=True, exist_ok=True)
    # Lecture seule : le verrou fonctionne même si le fichier appartient à un autre utilisateur.
    descripteur = os.open(VERROU, os.O_RDONLY | os.O_CREAT, 0o664)
    try:
        try:
            fcntl.flock(descripteur, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Un autre build est en cours : attente de sa fin…", flush=True)
            fcntl.flock(descripteur, fcntl.LOCK_EX)
        _tenu = True
        try:
            yield
        finally:
            _tenu = False
            fcntl.flock(descripteur, fcntl.LOCK_UN)
    finally:
        os.close(descripteur)
