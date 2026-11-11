#!/usr/bin/env bash
# Déploie nginx pour gauchiasses.fr SUR LE SERVEUR (Debian 13). À lancer en utilisateur normal (meli).
# Le script demande sudo pour apt, nginx et certbot.
#
# Usage :
#   ./deploy/deployer_nginx.sh --email toi@exemple.fr   # nginx + certificat Let's Encrypt + HTTPS
#   ./deploy/deployer_nginx.sh --sans-certificat        # HTTP seulement (pour tester ou avant le DNS)
#   ./deploy/deployer_nginx.sh --desinstaller           # retire le site de gauchiasses.fr de nginx
#
# Ce que fait le script, dans l'ordre :
#   1. installe nginx et certbot (apt) si besoin ;
#   2. vérifie que nginx peut lire public/ (sinon il s'arrête avec la commande à lancer) ;
#   3. écrit une configuration HTTP seule et la teste (nginx -t) ;
#   4. si le DNS de gauchiasses.fr pointe vers ce serveur, demande un certificat Let's Encrypt ;
#   5. écrit la configuration HTTPS, la teste, puis recharge nginx.
# En cas d'erreur à une étape, la configuration précédente est remise en place.
# Les autres sites nginx (ex. blog.zarisse.fr) ne sont pas modifiés.
set -euo pipefail

DOSSIER="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAINE="gauchiasses.fr"
RACINE="$DOSSIER/public"
DISPO="/etc/nginx/sites-available/$DOMAINE"
ACTIF="/etc/nginx/sites-enabled/$DOMAINE"
CERT_DIR="/etc/letsencrypt/live/$DOMAINE"
WEBROOT_ACME="/var/www/html"
EMAIL=""
SANS_CERT=0

# Page « Tu es banni » (fail2ban, nginx-geo-ban) : créée par fail2ban_hardened/f2b.sh sur le serveur.
# Incluse dans chaque bloc server seulement si elle existe : sinon nginx refuserait la configuration.
FAIL2BAN_SNIPPET="/etc/nginx/snippets/fail2ban-banni.conf"
if [[ -f "$FAIL2BAN_SNIPPET" ]]; then
    BAN_INCLUDE="    include $FAIL2BAN_SNIPPET; # fail2ban-banni"
else
    BAN_INCLUDE="    # fail2ban-banni absent : lance fail2ban_hardened/f2b.sh sur le serveur, puis relance ce script"
fi

info()    { printf '\033[1;34m[info]\033[0m %s\n' "$*"; }
avert()   { printf '\033[1;33m[attention]\033[0m %s\n' "$*"; }
erreur()  { printf '\033[1;31m[erreur]\033[0m %s\n' "$*" >&2; exit 1; }

if [[ "$EUID" -eq 0 && -z "${SUDO_USER:-}" ]]; then
    erreur "Lance ce script en utilisateur normal (meli), pas en root : il utilise sudo."
fi

MODE="installer"
while (( $# > 0 )); do
    case "$1" in
        --email) EMAIL="${2:-}"; shift 2 ;;
        --sans-certificat) SANS_CERT=1; shift ;;
        --desinstaller) MODE="desinstaller"; shift ;;
        *) erreur "Option inconnue : $1" ;;
    esac
done

# Écrit un fichier de configuration à partir de stdin, le teste, puis l'active.
# En cas d'échec de nginx -t, restaure l'ancien fichier (ou le supprime).
appliquer_config() {
    local tmp sauvegarde
    tmp="$(mktemp)"
    cat > "$tmp"
    sauvegarde="$(mktemp -u)"
    if [[ -f "$DISPO" ]]; then sudo cp -p "$DISPO" "$sauvegarde"; fi
    sudo install -m 644 "$tmp" "$DISPO"
    sudo ln -sfn "$DISPO" "$ACTIF"
    rm -f "$tmp"
    if ! sudo nginx -t 2>/tmp/nginx-test.$$; then
        cat /tmp/nginx-test.$$ >&2; rm -f /tmp/nginx-test.$$
        if [[ -f "$sauvegarde" ]]; then sudo cp -p "$sauvegarde" "$DISPO"; else sudo rm -f "$DISPO" "$ACTIF"; fi
        erreur "Configuration nginx invalide : l'état précédent a été rétabli."
    fi
    rm -f /tmp/nginx-test.$$
    sudo systemctl reload nginx
}

if [[ "$MODE" == "desinstaller" ]]; then
    info "Retrait du site $DOMAINE de nginx (les certificats sont conservés)"
    sudo rm -f "$ACTIF" "$DISPO"
    sudo nginx -t && sudo systemctl reload nginx
    info "Désinstallé."
    exit 0
fi

# 1. Paquets
manquants=()
for p in nginx certbot; do dpkg -s "$p" >/dev/null 2>&1 || manquants+=("$p"); done
if (( ${#manquants[@]} > 0 )); then
    info "Installation des paquets : ${manquants[*]}"
    sudo apt-get update
    sudo apt-get install -y "${manquants[@]}"
else
    info "nginx et certbot déjà installés"
fi

# 2. nginx doit pouvoir lire public/ (utilisateur www-data, traversée de /home/meli)
[[ -d "$RACINE" ]] || erreur "$RACINE absent : lance d'abord l'installation serveur (installer_serveur.sh)."
if ! sudo -u www-data test -x "$RACINE" || ! sudo -u www-data test -r "$RACINE"; then
    erreur "nginx (www-data) ne peut pas lire $RACINE. Il faut autoriser la traversée du dossier home, par exemple :
    sudo chmod o+x /home/$(id -un)
    (vérifie d'abord que ce changement te convient : il rend le dossier home traversable par tous, sans le lister)"
fi
[[ -f "$RACINE/index.html" ]] || avert "$RACINE/index.html n'existe pas encore : le site sera vide jusqu'à la première publication."

sudo mkdir -p "$WEBROOT_ACME/.well-known/acme-challenge"

# 3. Configuration HTTP seule : sert le site directement, sans redirection
info "Configuration HTTP seule"
appliquer_config <<EOF
# Généré par deploy/deployer_nginx.sh : ne pas éditer à la main (relancer le script).
server {
$BAN_INCLUDE
    listen 80;
    listen [::]:80;
    server_name $DOMAINE;

    root $RACINE;
    index index.html;

    location ^~ /.well-known/acme-challenge/ {
        root $WEBROOT_ACME;
    }

    location ~ /\. {
        deny all;
        return 404;
    }

    location / {
        try_files \$uri \$uri/ =404;
    }

    access_log /var/log/nginx/$DOMAINE.access.log;
    error_log  /var/log/nginx/$DOMAINE.error.log;
}
EOF
info "Site HTTP en ligne"

# 4. Certificat
IP_SERVEUR="$(hostname -I 2>/dev/null | awk '{print $1}')"  # IP locale, indicative seulement
IP_DNS="$(getent ahostsv4 "$DOMAINE" 2>/dev/null | awk 'NR==1{print $1}')"
if [[ -d "$CERT_DIR" ]]; then
    info "Certificat déjà présent dans $CERT_DIR"
elif (( SANS_CERT == 1 )); then
    info "Option --sans-certificat : pas de HTTPS pour l'instant"
elif [[ -z "$EMAIL" ]]; then
    avert "Pas d'adresse e-mail (--email) : pas de certificat. Relance avec --email pour activer le HTTPS."
elif [[ -z "$IP_DNS" ]]; then
    avert "Le DNS de $DOMAINE ne répond pas : certificat non demandé. Relance le script quand il est en place."
else
    # Derrière une box, le DNS donne l'IP publique et le serveur n'en connaît que l'IP locale :
    # on ne compare pas. On tente directement, et certbot dira si le domaine atteint le serveur.
    info "DNS de $DOMAINE : $IP_DNS (IP locale du serveur : $IP_SERVEUR, normal derrière une box)"
    info "Demande du certificat Let's Encrypt"
    if sudo certbot certonly --webroot -w "$WEBROOT_ACME" \
        -d "$DOMAINE" \
        --email "$EMAIL" --agree-tos --no-eff-email -n \
        --deploy-hook "systemctl reload nginx"; then
        info "Certificat obtenu"
    else
        avert "Échec de certbot : le site reste en HTTP. Voir /var/log/letsencrypt/letsencrypt.log"
    fi
fi

# 5. Configuration HTTPS, si le certificat existe
if [[ -d "$CERT_DIR" ]]; then
    info "Configuration HTTPS"
    appliquer_config <<EOF
# Généré par deploy/deployer_nginx.sh : ne pas éditer à la main (relancer le script).
server {
$BAN_INCLUDE
    listen 80;
    listen [::]:80;
    server_name $DOMAINE;

    location ^~ /.well-known/acme-challenge/ {
        root $WEBROOT_ACME;
    }

    location / {
        return 301 https://$DOMAINE\$request_uri;
    }
}

server {
$BAN_INCLUDE
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAINE;

    ssl_certificate     $CERT_DIR/fullchain.pem;
    ssl_certificate_key $CERT_DIR/privkey.pem;
    ssl_session_tickets off;

    root $RACINE;
    index index.html;

    # En-têtes de sécurité (always : aussi sur les réponses d'erreur).
    # Écrits ici en clair, sans fichier à inclure : le déploiement reste autonome.
    server_tokens off;
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
    # Pas de JavaScript sur le site : script-src 'self' suffit. Images : toute source HTTPS.
    add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; font-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'" always;

    # Site statique : seules les lectures sont acceptées
    if (\$request_method !~ ^(GET|HEAD)\$) {
        return 405;
    }

    location ~ /\. {
        deny all;
        return 404;
    }

    location / {
        try_files \$uri \$uri/ =404;
    }

    # add_header dans une location efface ceux du bloc server : on les répète ici
    location /veille/ {
        add_header Cache-Control "no-cache" always;
        add_header Strict-Transport-Security "max-age=31536000" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
        add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; font-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'" always;
    }

    access_log /var/log/nginx/$DOMAINE.access.log;
    error_log  /var/log/nginx/$DOMAINE.error.log;
}
EOF
    info "HTTPS actif sur https://$DOMAINE"
else
    info "Site en HTTP seulement pour l'instant : http://$DOMAINE"
fi

info "État : sudo nginx -t && systemctl status nginx --no-pager"
