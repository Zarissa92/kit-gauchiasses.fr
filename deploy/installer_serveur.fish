#!/usr/bin/env fish
# Même installation que installer_serveur.sh, pour fish. À lancer SUR LE SERVEUR, en utilisateur normal (meli).
#
# Usage, depuis le dossier du projet sur le serveur :
#   ./deploy/installer_serveur.fish                 # installe, active le timer, lance une première publication
#   ./deploy/installer_serveur.fish --desinstaller  # arrête et supprime le timer et le service

set -l DOSSIER (realpath (dirname (status filename))/..)
set -l UNITE gauchiasses-veille
set -l SERVICE_CIBLE /etc/systemd/system/$UNITE.service
set -l TIMER_CIBLE /etc/systemd/system/$UNITE.timer
set -l GROUPE (id -gn)

# Le script est lancé par l'utilisateur normal : SUDO_USER n'est pas défini (sauf si lancé via sudo)
set -l UTILISATEUR $USER
if set -q SUDO_USER; and test -n "$SUDO_USER"
    set UTILISATEUR $SUDO_USER
end

function info
    printf '\033[1;34m[info]\033[0m %s\n' $argv
end

function erreur
    printf '\033[1;31m[erreur]\033[0m %s\n' $argv >&2
    exit 1
end

if test (id -u) -eq 0; and not set -q SUDO_USER
    erreur "Lance ce script en utilisateur normal (meli), pas en root : il utilise sudo."
end

command -q systemctl; or erreur "systemd est requis."

if test "$argv[1]" = "--desinstaller"
    info "Arrêt et suppression de $UNITE.timer et $UNITE.service"
    sudo systemctl disable --now $UNITE.timer 2>/dev/null
    sudo systemctl stop $UNITE.service 2>/dev/null
    sudo rm -f $SERVICE_CIBLE $TIMER_CIBLE
    sudo systemctl daemon-reload
    info "Désinstallé. Le venv, public/ et data/ sont conservés."
    exit 0
end

if test -n "$argv[1]"
    erreur "Option inconnue : $argv[1] (seule --desinstaller est acceptée)"
end

# La base du garde immuable doit être là : sinon la page principale ne sera jamais publiée.
test -f $DOSSIER/data/immuable.json; or erreur "data/immuable.json absent : copie-le depuis ton PC (voir deploy/synchroniser.sh)."
test -f $DOSSIER/index.html; or erreur "index.html absent à la racine du projet."

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

# 2. Venv et dépendances
if not test -x $DOSSIER/venv/bin/python
    info "Création du venv dans $DOSSIER/venv"
    python3 -m venv $DOSSIER/venv
    or erreur "Création du venv impossible."
end
info "Installation de bin/requirements.txt"
$DOSSIER/venv/bin/pip install --upgrade pip -q
$DOSSIER/venv/bin/pip install -r $DOSSIER/bin/requirements.txt
or erreur "Installation de requirements.txt échouée."

# 3. Dossiers
mkdir -p $DOSSIER/public $DOSSIER/data

# 4. Unités systemd
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

# 5. Activation et première publication
sudo systemctl daemon-reload
sudo systemctl enable --now $UNITE.timer
info "Première publication (peut prendre quelques minutes à cause des aperçus)"
sudo systemctl start $UNITE.service; or info "La première publication a échoué : voir journalctl -u $UNITE.service"

info "Prochains passages :"
systemctl list-timers $UNITE.timer --no-pager; or true
info "Journal : journalctl -u $UNITE.service -n 50"
info "Pages publiées dans : $DOSSIER/public"
