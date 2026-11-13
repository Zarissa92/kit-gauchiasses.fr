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
#   2. crée le venv ./venv (à la racine) et y installe requirements.txt ;
#   3. crée la racine servie par nginx (racine_web de gauchiasses.cfg), data/ et build/ ;
#   4. installe gauchiasses-veille.service et .timer (modèles de deploy/systemd/) dans /etc/systemd/system ;
#   5. active le timer (intervalle_timer de gauchiasses.cfg) et lance une première publication.
#
# nginx n'est pas modifié par ce script : voir deploy/deployer_nginx.sh.
set -euo pipefail

DOSSIER="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$DOSSIER/deploy/lib_config.sh"  # cfg <section> <clé> : valeurs de gauchiasses.cfg
WEB_ROOT="$(cfg serveur racine_web)"
INTERVALLE="$(cfg serveur intervalle_timer)"
UTILISATEUR="${SUDO_USER:-$USER}"
if [[ "$EUID" -eq 0 && -z "${SUDO_USER:-}" ]]; then
    echo "Lance ce script en utilisateur normal (meli), pas en root : il utilise sudo." >&2
    exit 1
fi
GROUPE="$(id -gn "$UTILISATEUR")"  # groupe principal de l'utilisateur du service (pas celui de root, quand on lance via sudo)
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
    info "Désinstallé. Le venv, $WEB_ROOT, data/ et build/ sont conservés."
    exit 0
fi
[[ -z "${1:-}" ]] || erreur "Option inconnue : $1 (seule --desinstaller est acceptée)"

# La base du garde immuable doit être là : sinon la page principale ne sera jamais publiée.
[[ -f "$DOSSIER/data/immuable.json" ]] || erreur "data/immuable.json absent : copie-le depuis ton PC (fonction fish gauchiasses_update)."
[[ -f "$DOSSIER/accueil/index.html" ]] || erreur "accueil/index.html absent : copie le projet depuis ton PC (fonction fish gauchiasses_update)."

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
info "Installation de requirements.txt"
"$DOSSIER/venv/bin/pip" install --upgrade pip -q
"$DOSSIER/venv/bin/pip" install -r "$DOSSIER/requirements.txt"

# 3. Dossiers
# Racine servie par nginx : créée avec sudo (elle est hors du projet), puis rendue à l'utilisateur du service.
sudo mkdir -p "$WEB_ROOT"
# Rôles : www-data:www-data (nginx lit, le service écrit via le groupe). Dossiers en setgid 2775, fichiers en 664.
sudo chown -R www-data:www-data "$WEB_ROOT"
sudo find "$WEB_ROOT" -type d -exec chmod 2775 {} +
sudo find "$WEB_ROOT" -type f -exec chmod 664 {} +
# Le service (utilisateur $UTILISATEUR) doit appartenir au groupe www-data pour écrire dans WEB_ROOT.
sudo usermod -aG www-data "$UTILISATEUR"
mkdir -p "$DOSSIER/data" "$DOSSIER/build"
# Les dossiers du projet écrits par le service (données, site généré) appartiennent à l'utilisateur du service.
# Sans cela, un lancement précédent en root les laisse inaccessibles et la publication échoue
# (PermissionError à l'écriture de index.html.tmp).
sudo chown -R "$UTILISATEUR:$GROUPE" "$DOSSIER/data" "$DOSSIER/build"

# 4. Unités systemd
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
for fichier in "${UNITE}.service" "${UNITE}.timer"; do
    sed -e "s|__UTILISATEUR__|$UTILISATEUR|g" \
        -e "s|__GROUPE__|$GROUPE|g" \
        -e "s|__DOSSIER__|$DOSSIER|g" \
        -e "s|__RACINE_WEB__|$WEB_ROOT|g" \
        -e "s|__INTERVALLE__|$INTERVALLE|g" \
        "$DOSSIER/deploy/systemd/$fichier" > "$tmp/$fichier"
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
info "Site publié dans : $WEB_ROOT (toutes les $INTERVALLE)"
if [[ -d "$DOSSIER/public" ]]; then
    info "Ancienne racine web encore présente : $DOSSIER/public. Elle ne sert plus une fois nginx redéployé (deploy/deployer_nginx.sh) ; tu peux alors la supprimer."
fi
