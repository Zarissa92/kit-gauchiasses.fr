#!/usr/bin/env bash
# Vérifie la mise en ligne du site sur le serveur, et liste ce qui reste à faire à la main.
# Domaine, racine web et IP publique : lus dans gauchiasses.cfg.
# À lancer sur le serveur, en utilisateur normal (meli). sudo est demandé pour nginx et certbot.
#
# Usage :
#   ./deploy/verifier_serveur.sh               # contrôles locaux
#   ./deploy/verifier_serveur.sh --externe     # contrôle via l'IP publique (utile depuis l'extérieur seulement)
#
# Code de sortie : 0 si tout est OK, 1 si au moins un contrôle échoue.
set -uo pipefail

DOSSIER="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$DOSSIER/deploy/lib_config.sh"  # cfg <section> <clé> : valeurs de gauchiasses.cfg
DOMAINE="$(cfg site domaine)" || exit 1
IP_PUBLIQUE="$(cfg serveur ip_publique)" || exit 1
RACINE="$(cfg serveur racine_web)" || exit 1
CERT="/etc/letsencrypt/live/$DOMAINE/cert.pem"
ALERTE_CERT_JOURS=21
ALERTE_PUBLICATION_MIN=90

EXTERNE=0
[[ "${1:-}" == "--externe" ]] && EXTERNE=1

ok=0; ko=0
bon()   { printf '\033[1;32m[ OK ]\033[0m %s\n' "$*"; ok=$((ok+1)); }
mauvais() { printf '\033[1;31m[ KO ]\033[0m %s\n' "$*"; ko=$((ko+1)); }
attention() { printf '\033[1;33m[ ?? ]\033[0m %s\n' "$*"; }

# 1. DNS
ip_dns="$(getent ahostsv4 "$DOMAINE" 2>/dev/null | awk 'NR==1{print $1}')"
if [[ -n "$ip_dns" ]]; then
    bon "DNS $DOMAINE -> $ip_dns"
    [[ "$ip_dns" == "$IP_PUBLIQUE" ]] || attention "Attendu $IP_PUBLIQUE (ta box). Si ton DNS a changé, mets ip_publique à jour dans gauchiasses.cfg."
else
    mauvais "DNS $DOMAINE ne répond pas"
fi
if getent ahostsv4 "www.$DOMAINE" >/dev/null 2>&1; then
    bon "DNS www.$DOMAINE existe (pense à l'ajouter au certificat et au script nginx si besoin)"
else
    attention "www.$DOMAINE n'a pas de DNS : non servi, normal pour l'instant"
fi

# 2. nginx
if sudo nginx -t >/dev/null 2>&1; then
    bon "Configuration nginx valide"
else
    mauvais "Configuration nginx invalide : sudo nginx -t"
fi
if systemctl is-active --quiet nginx; then
    bon "nginx actif"
else
    mauvais "nginx inactif : sudo systemctl status nginx"
fi

# 3. Pages en HTTPS, testées sur le serveur lui-même
code_page="$(curl -s -m 10 -o /dev/null -w '%{http_code}' --resolve "$DOMAINE:443:127.0.0.1" "https://$DOMAINE/")"
[[ "$code_page" == "200" ]] && bon "Page principale en HTTPS (local) : 200" || mauvais "Page principale en HTTPS (local) : code $code_page"
code_veille="$(curl -s -m 10 -o /dev/null -w '%{http_code}' --resolve "$DOMAINE:443:127.0.0.1" "https://$DOMAINE/veille.html")"
[[ "$code_veille" == "200" ]] && bon "KiosKe (veille.html) en HTTPS (local) : 200" || mauvais "KiosKe (veille.html) en HTTPS (local) : code $code_veille"
code_http="$(curl -s -m 10 -o /dev/null -w '%{http_code}' --resolve "$DOMAINE:80:127.0.0.1" "http://$DOMAINE/")"
[[ "$code_http" == "301" ]] && bon "HTTP redirige vers HTTPS : 301" || mauvais "HTTP : code $code_http (301 attendu)"

# 4. Certificat
if [[ -f "$CERT" ]] || sudo test -f "$CERT"; then
    fin="$(sudo openssl x509 -enddate -noout -in "$CERT" | cut -d= -f2)"
    jours=$(( ( $(date -d "$fin" +%s) - $(date +%s) ) / 86400 ))
    if (( jours < ALERTE_CERT_JOURS )); then
        mauvais "Certificat : expire dans $jours jours ($fin)"
    else
        bon "Certificat valide encore $jours jours (expire le $fin)"
    fi
else
    mauvais "Certificat absent : relance deploy/deployer_nginx.sh --email ..."
fi
if sudo certbot renew --dry-run -q >/dev/null 2>&1; then
    bon "Renouvellement du certificat : test à blanc réussi"
else
    mauvais "Renouvellement du certificat en échec : sudo certbot renew --dry-run"
fi
systemctl is-active --quiet certbot.timer && bon "certbot.timer actif (renouvellement automatique)" || mauvais "certbot.timer inactif"

# 5. Publication automatique
systemctl is-active --quiet gauchiasses-veille.timer && bon "Timer de publication actif" || mauvais "Timer gauchiasses-veille inactif : ./deploy/installer_serveur.sh"
# veille.html est réécrite à chaque passage (index.html ne l'est que si la page principale a changé).
if [[ -f "$RACINE/veille.html" ]]; then
    age_min=$(( ( $(date +%s) - $(stat -c %Y "$RACINE/veille.html") ) / 60 ))
    if (( age_min > ALERTE_PUBLICATION_MIN )); then
        mauvais "Dernière publication il y a $age_min min : sudo journalctl -u gauchiasses-veille.service -n 50"
    else
        bon "Dernière publication il y a $age_min min"
    fi
else
    mauvais "$RACINE/veille.html absent"
fi
echo "    Prochain passage : $(systemctl list-timers gauchiasses-veille.timer --no-pager 2>/dev/null | sed -n 2p | awk '{print $1, $2}')"

# 6. Contrôle depuis l'extérieur (seulement si demandé : depuis le réseau local, la box ne renvoie pas le trafic)
if (( EXTERNE == 1 )); then
    code_ext="$(curl -s -m 15 -o /dev/null -w '%{http_code}' --resolve "$DOMAINE:443:$IP_PUBLIQUE" "https://$DOMAINE/")"
    [[ "$code_ext" == "200" ]] && bon "Accès via IP publique : 200" || mauvais "Accès via IP publique : code $code_ext (vérifie la redirection 80/443 de la box)"
fi

# 7. Ce qui ne peut pas être vérifié ici
echo
attention "À vérifier à la main : ouvrir https://$DOMAINE/ depuis ton téléphone en 4G (Wi-Fi coupé)."
echo
echo "Résultat : $ok OK, $ko erreur(s)."
(( ko == 0 ))
