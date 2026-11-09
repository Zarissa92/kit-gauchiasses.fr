#!/usr/bin/env bash
# Installation de la veille SUR LE SERVEUR (Debian 13), en utilisateur normal (meli).
# Le script demande sudo pour apt et systemd.
#
# Usage, depuis le dossier du projet sur le serveur :
#   ./deploy/installer_serveur.sh                 # installe, active le timer, lance une première publication
#   ./deploy/installer_serveur.sh --desinstaller  # arrête et supprime le timer et le service
#
# Ce que fait l'installation :
#   1. installe python3 et python3-venv (apt) si besoin ;
#   2. crée le venv ./venv (à la racine) et y installe bin/requirements.txt ;
#   3. crée public/ (racine servie par nginx) et data/ ;
#   4. installe gauchiasses-veille.service et .timer dans /etc/systemd/system ;
#   5. active le timer (toutes les 30 min) et lance une première publication.
#
# nginx n'est pas modifié par ce script : voir deploy/nginx-gauchiasses.conf.
set -euo pipefail

DOSSIER="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UTILISATEUR="${SUDO_USER:-$USER}"
if [[ "$EUID" -eq 0 && -z "${SUDO_USER:-}" ]]; then
    echo "Lance ce script en utilisateur normal (meli), pas en root : il utilise sudo." >&2
    exit 1
fi
GROUPE="$(id -gn)"
UNITE="gauchiasses-veille"
SERVICE_CIBLE="/etc/systemd/system/${UNITE}.service"
TIMER_CIBLE="/etc/systemd/system/${UNITE}.timer"

info() { printf '\033[1;34m[info]\033[0m %s\n' "$*"; }
erreur() { printf '\033[1;31m[erreur]\033[0m %s\n' "$*" >&2; exit 1; }

command -v systemctl >/dev/null || erreur "systemd est requis."

if [[ "${1:-}" == "--desinstaller" ]]; then
    info "Arrêt et suppression de ${UNITE}.timer et ${UNITE}.service"
    sudo systemctl disable --now "${UNITE}.timer" 2>/dev/null || true
    sudo systemctl stop "${UNITE}.service" 2>/dev/null || true
    sudo rm -f "$SERVICE_CIBLE" "$TIMER_CIBLE"
    sudo systemctl daemon-reload
    info "Désinstallé. Le venv, public/ et data/ sont conservés."
    exit 0
fi
[[ -z "${1:-}" ]] || erreur "Option inconnue : $1 (seule --desinstaller est acceptée)"

# La base du garde immuable doit être là : sinon la page principale ne sera jamais publiée.
[[ -f "$DOSSIER/data/immuable.json" ]] || erreur "data/immuable.json absent : copie-le depuis ton PC (voir deploy/synchroniser.sh)."
[[ -f "$DOSSIER/index.html" ]] || erreur "index.html absent à la racine du projet."

# 1. Paquets système
manquants=()
for p in python3 python3-venv; do
    dpkg -s "$p" >/dev/null 2>&1 || manquants+=("$p")
done
if (( ${#manquants[@]} > 0 )); then
    info "Installation des paquets : ${manquants[*]}"
    sudo apt-get update
    sudo apt-get install -y "${manquants[@]}"
else
    info "Paquets système déjà présents"
fi

# 2. Venv et dépendances
if [[ ! -x "$DOSSIER/venv/bin/python" ]]; then
    info "Création du venv dans $DOSSIER/venv"
    python3 -m venv "$DOSSIER/venv"
fi
info "Installation de bin/requirements.txt"
"$DOSSIER/venv/bin/pip" install --upgrade pip -q
"$DOSSIER/venv/bin/pip" install -r "$DOSSIER/bin/requirements.txt"

# 3. Dossiers
mkdir -p "$DOSSIER/public" "$DOSSIER/data"

# 4. Unités systemd
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
for fichier in "${UNITE}.service" "${UNITE}.timer"; do
    sed -e "s|__UTILISATEUR__|$UTILISATEUR|g" \
        -e "s|__GROUPE__|$GROUPE|g" \
        -e "s|__DOSSIER__|$DOSSIER|g" \
        "$DOSSIER/bin/$fichier" > "$tmp/$fichier"
done
sudo install -m 644 "$tmp/${UNITE}.service" "$SERVICE_CIBLE"
sudo install -m 644 "$tmp/${UNITE}.timer" "$TIMER_CIBLE"
info "Unités installées dans /etc/systemd/system"

# 5. Activation et première publication
sudo systemctl daemon-reload
sudo systemctl enable --now "${UNITE}.timer"
info "Première publication (peut prendre quelques minutes à cause des aperçus)"
sudo systemctl start "${UNITE}.service" || info "La première publication a échoué : voir journalctl -u ${UNITE}.service"

info "Prochains passages :"
systemctl list-timers "${UNITE}.timer" --no-pager || true
info "Journal : journalctl -u ${UNITE}.service -n 50"
info "Pages publiées dans : $DOSSIER/public"
