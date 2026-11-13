#!/usr/bin/env bash
# Déploie nginx pour le site SUR LE SERVEUR (Debian 13). À lancer en utilisateur normal (meli).
# Domaine et racine web : lus dans gauchiasses.cfg.
# Le script demande sudo pour apt, nginx et certbot.
#
# Usage :
#   ./deploy/deployer_nginx.sh --email toi@exemple.fr   # nginx + certificat Let's Encrypt + HTTPS
#   ./deploy/deployer_nginx.sh --sans-certificat        # HTTP seulement (pour tester ou avant le DNS)
#   ./deploy/deployer_nginx.sh --desinstaller           # retire le site de nginx
#
# Ce que fait le script, dans l'ordre :
#   1. installe nginx et certbot (apt) si besoin ;
#   2. vérifie que nginx peut lire la racine web (sinon il s'arrête avec la commande à lancer) ;
#   3. écrit une configuration HTTP seule (avec les protections ci-dessous) et la teste (nginx -t) ;
#   4. si le DNS du domaine pointe vers ce serveur, demande un certificat Let's Encrypt ;
#   5. écrit la configuration HTTPS, la teste, puis recharge nginx.
# En cas d'erreur à une étape, la configuration précédente est remise en place.
# Les autres sites nginx (ex. blog.zarisse.fr) ne sont pas modifiés.
#
# Protections écrites dans la configuration (voir README, « Sécurité nginx ») :
#   - HTTPS seul (HSTS), TLS 1.3 seul, courbes X25519/secp384r1, 0-RTT refusé ;
#   - version de nginx masquée, méthodes limitées à GET et HEAD ;
#   - en-têtes de sécurité, politique de contenu : aucun script, aucune police ni feuille de style d'un autre site ;
#     les images d'un autre site ne sont acceptées qu'en HTTPS (cartes Wikipédia de la page principale) ;
#   - fichiers cachés refusés ;
#   - si la page de ban fail2ban est installée (deploy/fail2ban/), elle est incluse dans chaque site.
set -euo pipefail

DOSSIER="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$DOSSIER/deploy/lib_config.sh"  # cfg <section> <clé> : valeurs de gauchiasses.cfg
DOMAINE="$(cfg site domaine)"
RACINE="$(cfg serveur racine_web)"  # racine servie : la même que la publication
DISPO="/etc/nginx/sites-available/$DOMAINE"
ACTIF="/etc/nginx/sites-enabled/$DOMAINE"
CERT_DIR="/etc/letsencrypt/live/$DOMAINE"
WEBROOT_ACME="/var/www/html"
SNIPPET_BAN="/etc/nginx/snippets/fail2ban-banni.conf"
EMAIL=""
SANS_CERT=0

# Politique de contenu : aucun script, et rien d'un autre site sauf des images en HTTPS.
# Le KiosKe ne charge que des images du site (téléchargées par le build, servies depuis img/veille/).
# La page principale affiche les images de Wikipédia (cartes et bloc immuable) : d'où « https: » dans img-src.
CSP="default-src 'none'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; font-src 'self'; script-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"

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

# 2. nginx (www-data) doit pouvoir lire la racine web
[[ -d "$RACINE" ]] || erreur "$RACINE absent : lance d'abord l'installation serveur (installer_serveur.sh)."
if ! sudo -u www-data test -x "$RACINE" || ! sudo -u www-data test -r "$RACINE"; then
    erreur "nginx (www-data) ne peut pas lire $RACINE. Relance deploy/installer_serveur.sh (il crée ce dossier avec les bons droits)."
fi
[[ -f "$RACINE/index.html" ]] || avert "$RACINE/index.html n'existe pas encore : le site sera vide jusqu'à la première publication."

sudo mkdir -p "$WEBROOT_ACME/.well-known/acme-challenge"

# Blocs communs aux deux configurations (HTTP et HTTPS), écrits dans les heredocs ci-dessous.
# Si la page de ban fail2ban existe, elle est incluse : sinon nginx -t échouerait.
if [[ -f "$SNIPPET_BAN" ]]; then
    INCLUDE_BAN="    include $SNIPPET_BAN; # fail2ban-banni"
else
    INCLUDE_BAN="    # page de ban fail2ban absente : lancer deploy/gauchiasses.sh fail2ban, puis relancer ce script"
fi
PROTECTIONS="    # Ne pas annoncer la version de nginx
    server_tokens off;

    # Site statique : seules les lectures sont acceptées
    if (\$request_method !~ ^(GET|HEAD)\$) {
        return 405;
    }

    # En-têtes de sécurité (always : aussi sur les réponses d'erreur)
    add_header X-Content-Type-Options \"nosniff\" always;
    add_header X-Frame-Options \"SAMEORIGIN\" always;
    add_header Referrer-Policy \"strict-origin-when-cross-origin\" always;
    add_header Permissions-Policy \"camera=(), microphone=(), geolocation=(), payment=()\" always;
    add_header Content-Security-Policy \"$CSP\" always;"

# 3. Configuration HTTP seule : sert le site directement, sans redirection
info "Configuration HTTP seule"
appliquer_config <<EOF
# Généré par deploy/deployer_nginx.sh : ne pas éditer à la main (relancer le script).
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAINE;

$INCLUDE_BAN

$PROTECTIONS

    root $RACINE;
    index index.html;

    location ^~ /.well-known/acme-challenge/ {
        root $WEBROOT_ACME;
    }

    # Fichiers cachés (.git, .env…) : refusés
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
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name $DOMAINE;

$INCLUDE_BAN

    ssl_certificate     $CERT_DIR/fullchain.pem;
    ssl_certificate_key $CERT_DIR/privkey.pem;
    # TLS 1.3 seul : TLS 1.0, 1.1 et 1.2 sont refusés. (Pour réaccepter 1.2, ajouter « TLSv1.2 » ici.)
    ssl_protocols       TLSv1.3;
    # Courbes elliptiques modernes uniquement ; pas de DH classique, pas de reprise de session par ticket.
    ssl_ecdh_curve      X25519:secp384r1;
    ssl_prefer_server_ciphers off;
    ssl_session_tickets off;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;
    # 0-RTT (early data) refusé : pas de rejeu possible.
    ssl_early_data      off;

    # HTTPS seul, pendant un an
    add_header Strict-Transport-Security "max-age=31536000" always;

$PROTECTIONS

    root $RACINE;
    index index.html;

    # Fichiers cachés (.git, .env…) : refusés
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
    info "HTTPS actif sur https://$DOMAINE"
else
    info "Site en HTTP seulement pour l'instant : http://$DOMAINE"
fi

info "État : sudo nginx -t && systemctl status nginx --no-pager"
