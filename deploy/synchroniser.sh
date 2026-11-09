#!/usr/bin/env bash
# Copie le projet de ton PC vers le serveur (rsync via SSH). À lancer depuis le PC.
#
# Usage :
#   ./deploy/synchroniser.sh                       # vers meli@192.168.1.13:/home/meli/gauchiasses.fr/
#   ./deploy/synchroniser.sh --simuler             # affiche ce qui serait copié, sans rien copier
#   ./deploy/synchroniser.sh meli@autre-hote:/chemin/
#
# Ce qui n'est PAS copié :
#   - venv/, venv_blog/ : créés sur le serveur ;
#   - data/historique.db : l'historique vit sur le serveur ;
#   - veille/ et public/ : produits par le serveur ;
#   - data/cache/ : caches du build des cartes (regénérés au besoin) ;
#   - export/ : copie locale de contrôle, pas de la prod ;
#   - old/, .git/, .directory, caches Python.
# Pas de --delete : un fichier supprimé ici n'est pas supprimé sur le serveur.
set -euo pipefail

DEST_DEFAUT="meli@192.168.1.13:/home/meli/gauchiasses.fr/"
SIMULER=""
if [[ "${1:-}" == "--simuler" ]]; then
    SIMULER="--dry-run"
    shift
fi
DEST="${1:-$DEST_DEFAUT}"

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v rsync >/dev/null || { echo "rsync est requis." >&2; exit 1; }

echo "Source : $RACINE/"
echo "Cible  : $DEST"
rsync -av $SIMULER \
    --exclude 'venv/' \
    --exclude 'venv_blog/' \
    --exclude 'data/historique.db' \
    --exclude 'veille/' \
    --exclude 'public/' \
    --exclude 'old/' \
    --exclude 'data/cache/' \
    --exclude 'export/' \
    --exclude '.git/' \
    --exclude '.directory' \
    --exclude '__pycache__/' \
    "$RACINE/" "$DEST"
echo "OK"
