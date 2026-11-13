#!/usr/bin/env bash
# gauchiasses.sh — déploiement de gauchiasses.fr. Un seul point d'entrée pour toutes les parties.
#
# Sans argument, déploie TOUT, dans cet ordre. Chaque étape s'arrête à sa première erreur :
#   immuable   le bloc immuable doit être enregistré (sinon rien n'est publié)
#   serveur    venv et timer de publication (installer_serveur.sh)
#   veille     construit le site dans build/ (pages, flux, images), puis le publie dans la racine web
#   nginx      configure le site : HTTP, puis HTTPS si le certificat existe (deployer_nginx.sh)
#   fail2ban   page « Tu es banni » et jail gauchiasses-scan ; étape ignorée si la jail sans_pitie manque
#   statut     contrôle final (verifier_serveur.sh), sans bloquer le déploiement
#
# Usage :
#   deploy/gauchiasses.sh                          # tout
#   deploy/gauchiasses.sh --email toi@exemple.fr   # tout, et demande le certificat Let's Encrypt
#   deploy/gauchiasses.sh --sans-certificat        # tout, HTTP seulement (nginx)
#   deploy/gauchiasses.sh veille nginx             # seulement ces étapes, dans l'ordre donné
#   deploy/gauchiasses.sh --simulation             # affiche ce qui serait fait, sans rien lancer
#   deploy/gauchiasses.sh aide
#
# Étapes : immuable, serveur, veille, nginx, fail2ban, statut.
# À lancer sur le serveur, en utilisateur normal (meli) : les étapes qui en ont besoin demandent sudo.
# Jamais le Python système : le venv du projet (venv/ sur le serveur, venv_blog/ sur le PC) est utilisé.
# Domaine et racine web : lus dans gauchiasses.cfg.
set -Eeuo pipefail

DOSSIER="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$DOSSIER/deploy/lib_config.sh"  # cfg <section> <clé> : valeurs de gauchiasses.cfg
DOMAINE="$(cfg site domaine)"
RACINE_WEB="$(cfg serveur racine_web)"
SITE_NGINX="/etc/nginx/sites-available/$DOMAINE"
CERT_DIR="/etc/letsencrypt/live/$DOMAINE"
LOG_NGINX="/var/log/nginx/$DOMAINE.access.log"
FILTRE_F2B="/etc/fail2ban/filter.d/gauchiasses-scan.conf"
JAIL_F2B="/etc/fail2ban/jail.d/gauchiasses-scan.local"
JAIL_PREREQUIS="sans_pitie"

EMAIL=""
SANS_CERT=0
SIMULATION=0
ETAPES=()
ETAPES_TOUT=(immuable serveur veille nginx fail2ban statut)

info()   { printf '\033[1;34m[info]\033[0m %s\n' "$*"; }
ok()     { printf '\033[1;32m[ok]\033[0m %s\n' "$*"; }
avert()  { printf '\033[1;33m[attention]\033[0m %s\n' "$*"; }
erreur() { printf '\033[1;31m[erreur]\033[0m %s\n' "$*" >&2; exit 1; }

aide() {
    sed -n '2,23p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# Lance une commande, ou l'affiche seulement en simulation.
lancer() {
    if (( SIMULATION == 1 )); then
        printf '  [simulation] %s\n' "$*"
    else
        "$@"
    fi
}

# Le Python du projet : venv/ sur le serveur, venv_blog/ sur le PC. Jamais le Python système.
python_projet() {
    if [[ -x "$DOSSIER/venv/bin/python" ]]; then
        echo "$DOSSIER/venv/bin/python"
    elif [[ -x "$DOSSIER/venv_blog/bin/python" ]]; then
        echo "$DOSSIER/venv_blog/bin/python"
    else
        erreur "Aucun venv du projet (venv/ ou venv_blog/). Lance d'abord deploy/installer_serveur.sh."
    fi
}

# ---------- Étapes ----------

etape_immuable() {
    info "Bloc immuable : vérification de l'empreinte"
    lancer "$(python_projet)" "$DOSSIER/bin/garde_immuable.py" verifier
}

etape_serveur() {
    info "Serveur : venv et timer de publication"
    lancer bash "$DOSSIER/deploy/installer_serveur.sh"
}

etape_veille() {
    info "Veille : construction du site (pages, flux, images), puis publication dans $RACINE_WEB"
    lancer "$(python_projet)" "$DOSSIER/bin/publier_public.py"
}

etape_nginx() {
    info "nginx : configuration du site $DOMAINE"
    local args=()
    if [[ -n "$EMAIL" ]]; then
        args+=(--email "$EMAIL")
    elif (( SANS_CERT == 1 )); then
        args+=(--sans-certificat)
    fi
    lancer bash "$DOSSIER/deploy/deployer_nginx.sh" "${args[@]}"
}

etape_fail2ban() {
    info "fail2ban : page « Tu es banni » et jail gauchiasses-scan"
    if (( SIMULATION == 1 )); then
        printf '  [simulation] f2b.sh (si la jail %s existe), puis installation du filtre et de la jail gauchiasses-scan\n' "$JAIL_PREREQUIS"
        return 0
    fi
    if ! command -v fail2ban-client >/dev/null 2>&1; then
        avert "fail2ban n'est pas installé (sudo apt-get install fail2ban). Étape ignorée."
        return 0
    fi
    if ! sudo fail2ban-client status "$JAIL_PREREQUIS" >/dev/null 2>&1; then
        avert "La jail [$JAIL_PREREQUIS] n'existe pas dans /etc/fail2ban/jail.d/hardening.local : étape ignorée."
        return 0
    fi
    [[ -f "$SITE_NGINX" ]] || erreur "$SITE_NGINX absent : l'étape nginx doit réussir avant fail2ban."

    # 1. Page de ban et action nginx-geo-ban (f2b.sh est idempotent)
    sudo bash "$DOSSIER/deploy/fail2ban/f2b.sh" "$SITE_NGINX"

    # 2. Filtre : test sur le journal réel, puis installation
    if sudo test -f "$LOG_NGINX"; then
        sudo fail2ban-regex "$LOG_NGINX" "$DOSSIER/deploy/fail2ban/gauchiasses-scan.conf" | tail -n 4 || true
    else
        avert "$LOG_NGINX absent : le test du filtre est sauté (il sera créé à la première visite)."
    fi
    sudo install -m 644 "$DOSSIER/deploy/fail2ban/gauchiasses-scan.conf" "$FILTRE_F2B"

    # 3. Jail : sauvegarde de l'ancienne, puis rechargement. Si fail2ban refuse, on revient en arrière.
    if [[ -f "$JAIL_F2B" ]]; then sudo cp -p "$JAIL_F2B" "$JAIL_F2B.avant"; fi
    # Le journal surveillé porte le nom du domaine (gauchiasses.cfg).
    sed "s|__DOMAINE__|$DOMAINE|g" "$DOSSIER/deploy/fail2ban/gauchiasses-scan.jail.conf" | sudo install -m 644 /dev/stdin "$JAIL_F2B"
    if ! sudo fail2ban-client reload; then
        avert "fail2ban a refusé la nouvelle jail : retour à l'état précédent."
        if [[ -f "$JAIL_F2B.avant" ]]; then sudo mv -f "$JAIL_F2B.avant" "$JAIL_F2B"; else sudo rm -f "$JAIL_F2B"; fi
        sudo fail2ban-client reload || true
        erreur "Jail gauchiasses-scan non installée."
    fi
    sudo fail2ban-client status gauchiasses-scan | sed 's/^/  /'
    ok "fail2ban configuré"
}

etape_statut() {
    info "Statut : contrôle de la mise en ligne"
    if (( SIMULATION == 1 )); then
        printf '  [simulation] bash deploy/verifier_serveur.sh\n'
        return 0
    fi
    bash "$DOSSIER/deploy/verifier_serveur.sh" || avert "Le contrôle signale des points à vérifier (voir ci-dessus)."
}

# ---------- Lecture des options ----------

while (( $# > 0 )); do
    case "$1" in
        aide|-h|--help) aide; exit 0 ;;
        --email) EMAIL="${2:-}"; [[ -n "$EMAIL" ]] || erreur "--email attend une adresse"; shift 2 ;;
        --sans-certificat) SANS_CERT=1; shift ;;
        --simulation) SIMULATION=1; shift ;;
        immuable|serveur|veille|nginx|fail2ban|statut) ETAPES+=("$1"); shift ;;
        *) erreur "Option ou étape inconnue : $1 (voir deploy/gauchiasses.sh aide)" ;;
    esac
done

if (( ${#ETAPES[@]} == 0 )); then
    ETAPES=("${ETAPES_TOUT[@]}")
    info "Aucune étape indiquée : déploiement complet (${ETAPES[*]})"
fi
if (( SIMULATION == 1 )); then
    avert "Simulation : aucune commande ne sera lancée."
fi

# ---------- Exécution ----------

for etape in "${ETAPES[@]}"; do
    "etape_$etape"
done

if (( SIMULATION == 1 )); then
    ok "Simulation terminée."
else
    ok "Déploiement terminé : ${ETAPES[*]}"
fi
