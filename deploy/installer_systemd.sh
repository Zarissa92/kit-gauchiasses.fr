#!/usr/bin/env bash
# Installe la publication automatique de la veille (toutes les 30 min) avec systemd.
#
# Usage (en utilisateur normal, le script demande sudo quand il en a besoin) :
#   ./deploy/installer_systemd.sh               # installe et active le timer
#   ./deploy/installer_systemd.sh --desinstaller  # arrête et supprime le service et le timer
#
# Ce que fait l'installation :
#   1. installe python3 et python3-venv (apt) si besoin ;
#   2. crée le venv ./venv (à la racine) et y installe bin/requirements.txt ;
#   3. restreint publish_site.py (il contient le mot de passe FTP) à ton utilisateur ;
#   4. installe gauchiasses-veille.service et .timer dans /etc/systemd/system ;
#   5. active le timer.
set -euo pipefail

DOSSIER="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # racine du projet
UTILISATEUR="${SUDO_USER:-$USER}"
GROUPE="$(id -gn "$UTILISATEUR")"
UNITE="gauchiasses-veille"
SERVICE_CIBLE="/etc/systemd/system/${UNITE}.service"
TIMER_CIBLE="/etc/systemd/system/${UNITE}.timer"

info() { printf '\033[1;34m[info]\033[0m %s\n' "$*"; }
erreur() { printf '\033[1;31m[erreur]\033[0m %s\n' "$*" >&2; exit 1; }

if [[ "$EUID" -eq 0 && -z "${SUDO_USER:-}" ]]; then
    erreur "Lance ce script en utilisateur normal, pas directement en root (il utilise sudo)."
fi

if ! grep -qi '^ID=debian' /etc/os-release 2>/dev/null; then
    info "Système non Debian détecté : le script est prévu pour Debian, vérifie apt et systemd."
fi

command -v systemctl >/dev/null || erreur "systemd est requis."

desinstaller() {
    info "Arrêt et suppression de ${UNITE}.timer et ${UNITE}.service"
    sudo systemctl disable --now "${UNITE}.timer" 2>/dev/null || true
    sudo systemctl stop "${UNITE}.service" 2>/dev/null || true
    sudo rm -f "$SERVICE_CIBLE" "$TIMER_CIBLE"
    sudo systemctl daemon-reload
    info "Désinstallé. Le venv et les fichiers du projet sont conservés."
    exit 0
}

if [[ "${1:-}" == "--desinstaller" ]]; then
    desinstaller
fi

[[ "${1:-}" == "" ]] || erreur "Option inconnue : $1 (seule --desinstaller est acceptée)"

# 1. Paquets système
paquets=(python3 python3-venv)
manquants=()
for p in "${paquets[@]}"; do
    dpkg -s "$p" >/dev/null 2>&1 || manquants+=("$p")
done
if (( ${#manquants[@]} > 0 )); then
    info "Installation des paquets : ${manquants[*]}"
    sudo apt-get update
    sudo apt-get install -y "${manquants[@]}"
else
    info "Paquets système déjà présents"
fi

# 2. Venv et dépendances (exécutés en tant que l'utilisateur, pas en root)
if [[ ! -x "$DOSSIER/venv/bin/python" ]]; then
    info "Création du venv dans $DOSSIER/venv"
    sudo -u "$UTILISATEUR" python3 -m venv "$DOSSIER/venv"
fi
info "Installation de requirements.txt"
sudo -u "$UTILISATEUR" "$DOSSIER/venv/bin/pip" install --upgrade pip -q
sudo -u "$UTILISATEUR" "$DOSSIER/venv/bin/pip" install -r "$DOSSIER/bin/requirements.txt"

# 3. Le script contient le mot de passe FTP : lisible par l'utilisateur seul
info "Restriction de publish_site.py à $UTILISATEUR (chmod 600)"
sudo chown "$UTILISATEUR:$GROUPE" "$DOSSIER/bin/publish_site.py"
sudo chmod 600 "$DOSSIER/bin/publish_site.py"

# 4. Unités systemd, avec le bon utilisateur et le bon dossier
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

# 5. Activation
sudo systemctl daemon-reload
sudo systemctl enable --now "${UNITE}.timer"

info "Timer actif. Prochains passages :"
systemctl list-timers "${UNITE}.timer" --no-pager || true
info "Journal : journalctl -u ${UNITE}.service -n 50"
info "Test immédiat : sudo systemctl start ${UNITE}.service"
