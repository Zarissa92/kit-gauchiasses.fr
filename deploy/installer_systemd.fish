#!/usr/bin/env fish
# Même installation que installer_systemd.sh, pour fish.
# Installe la publication automatique de la veille (toutes les 30 min) avec systemd.
#
# Usage (en utilisateur normal, le script demande sudo quand il en a besoin) :
#   ./deploy/installer_systemd.fish                  # installe et active le timer
#   ./deploy/installer_systemd.fish --desinstaller   # arrête et supprime le service et le timer

set -l DOSSIER (realpath (dirname (status filename))/..)  # racine du projet
set -l UNITE gauchiasses-veille
set -l SERVICE_CIBLE /etc/systemd/system/$UNITE.service
set -l TIMER_CIBLE /etc/systemd/system/$UNITE.timer

set -l UTILISATEUR $USER
if set -q SUDO_USER; and test -n "$SUDO_USER"
    set UTILISATEUR $SUDO_USER
end
set -l GROUPE (id -gn $UTILISATEUR)

function info
    printf '\033[1;34m[info]\033[0m %s\n' $argv
end

function erreur
    printf '\033[1;31m[erreur]\033[0m %s\n' $argv >&2
    exit 1
end

if test (id -u) -eq 0; and not set -q SUDO_USER
    erreur "Lance ce script en utilisateur normal, pas directement en root (il utilise sudo)."
end

if not grep -qi '^ID=debian' /etc/os-release 2>/dev/null
    info "Système non Debian détecté : le script est prévu pour Debian, vérifie apt et systemd."
end

command -q systemctl; or erreur "systemd est requis."

if test "$argv[1]" = "--desinstaller"
    info "Arrêt et suppression de $UNITE.timer et $UNITE.service"
    sudo systemctl disable --now $UNITE.timer 2>/dev/null
    sudo systemctl stop $UNITE.service 2>/dev/null
    sudo rm -f $SERVICE_CIBLE $TIMER_CIBLE
    sudo systemctl daemon-reload
    info "Désinstallé. Le venv et les fichiers du projet sont conservés."
    exit 0
end

if test -n "$argv[1]"
    erreur "Option inconnue : $argv[1] (seule --desinstaller est acceptée)"
end

# 1. Paquets système
set -l manquants
for p in python3 python3-venv
    dpkg -s $p >/dev/null 2>&1; or set -a manquants $p
end
if test (count $manquants) -gt 0
    info "Installation des paquets : $manquants"
    sudo apt-get update
    or erreur "apt-get update a échoué."
    sudo apt-get install -y $manquants
    or erreur "L'installation des paquets a échoué."
else
    info "Paquets système déjà présents"
end

# 2. Venv et dépendances (en tant que l'utilisateur, pas en root)
if not test -x $DOSSIER/venv/bin/python
    info "Création du venv dans $DOSSIER/venv"
    sudo -u $UTILISATEUR python3 -m venv $DOSSIER/venv
    or erreur "Création du venv impossible."
end
info "Installation de requirements.txt"
sudo -u $UTILISATEUR $DOSSIER/venv/bin/pip install --upgrade pip -q
sudo -u $UTILISATEUR $DOSSIER/venv/bin/pip install -r $DOSSIER/bin/requirements.txt
or erreur "Installation de requirements.txt échouée."

# 3. publish_site.py contient le mot de passe FTP : lisible par l'utilisateur seul
info "Restriction de publish_site.py à $UTILISATEUR (chmod 600)"
sudo chown "$UTILISATEUR:$GROUPE" $DOSSIER/bin/publish_site.py
sudo chmod 600 $DOSSIER/bin/publish_site.py

# 4. Unités systemd, avec le bon utilisateur et le bon dossier
set -l tmp (mktemp -d)
for fichier in $UNITE.service $UNITE.timer
    sed -e "s|__UTILISATEUR__|$UTILISATEUR|g" \
        -e "s|__GROUPE__|$GROUPE|g" \
        -e "s|__DOSSIER__|$DOSSIER|g" \
        $DOSSIER/bin/$fichier > $tmp/$fichier
end
sudo install -m 644 $tmp/$UNITE.service $SERVICE_CIBLE
sudo install -m 644 $tmp/$UNITE.timer $TIMER_CIBLE
rm -rf $tmp
info "Unités installées dans /etc/systemd/system"

# 5. Activation
sudo systemctl daemon-reload
sudo systemctl enable --now $UNITE.timer

info "Timer actif. Prochains passages :"
systemctl list-timers $UNITE.timer --no-pager; or true
info "Journal : journalctl -u $UNITE.service -n 50"
info "Test immédiat : sudo systemctl start $UNITE.service"
