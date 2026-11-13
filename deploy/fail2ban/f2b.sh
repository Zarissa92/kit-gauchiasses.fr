#!/usr/bin/env bash
# f2b.sh — Blocage nginx "Tu es banni" pour la jail sans_pitie (Debian 13)
# SPDX-License-Identifier: GPL-3.0-or-later
# Usage : sudo ./f2b.sh /chemin/vers/le/fichier/site
set -Eeuo pipefail

SITE_CONF="${1:-}"
JAIL_FILE="/etc/fail2ban/jail.d/hardening.local"
ACTION_FILE="/etc/fail2ban/action.d/nginx-geo-ban.conf"
GEO_FILE="/etc/nginx/conf.d/banned.conf"
BANNED_LIST="/etc/nginx/banned_ips.conf"
SNIPPET="/etc/nginx/snippets/fail2ban-banni.conf"
INCLUDE_LINE="    include ${SNIPPET}; # fail2ban-banni"

if [[ $EUID -ne 0 ]]; then
    echo "Lancez ce script en root (sudo)." >&2
    exit 1
fi
if [[ -z "$SITE_CONF" || ! -f "$SITE_CONF" ]]; then
    echo "Usage : sudo $0 /chemin/vers/le/fichier/site" >&2
    exit 1
fi
if [[ ! -f "$JAIL_FILE" ]] || ! grep -q '^\[sans_pitie\]' "$JAIL_FILE"; then
    echo "La jail sans_pitie est introuvable dans $JAIL_FILE. Lancez d'abord le script de déploiement fail2ban." >&2
    exit 1
fi
if ! command -v nginx >/dev/null 2>&1; then
    echo "nginx n'est pas installé." >&2
    exit 1
fi

MANAGED=("$SITE_CONF" "$JAIL_FILE" "$ACTION_FILE" "$GEO_FILE" "$BANNED_LIST" "$SNIPPET")

# ---------- sauvegarde ----------
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="/root/banni-backup-${STAMP}"
mkdir -p "$BACKUP_DIR" /etc/nginx/snippets /etc/nginx/conf.d /etc/fail2ban/action.d
for f in "${MANAGED[@]}"; do
    if [[ -f "$f" ]]; then
        cp -a "$f" "$BACKUP_DIR/managed-$(basename "$f")"
    fi
done
echo "Sauvegarde : $BACKUP_DIR"

# ---------- restauration ----------
rollback() {
    trap - ERR
    echo "Restauration de la configuration précédente..." >&2
    for f in "${MANAGED[@]}"; do
        local b="$BACKUP_DIR/managed-$(basename "$f")"
        if [[ -f "$b" ]]; then
            cp -a "$b" "$f"
        else
            rm -f "$f"
        fi
    done
    if nginx -t >/dev/null 2>&1; then
        systemctl reload nginx || true
    fi
    systemctl restart fail2ban || true
}

on_error() {
    echo "Erreur à la ligne $1, arrêt." >&2
    rollback
    exit 1
}
trap 'on_error $LINENO' ERR

# ---------- action fail2ban ----------
# Précédence corrigée : écriture du fichier et validation/reload sont deux étapes distinctes
cat > "$ACTION_FILE" <<'EOF'
[Definition]
actionstart =
actionstop =
actioncheck =
actionban = grep -qF "<ip> 1;" /etc/nginx/banned_ips.conf || echo "<ip> 1;" >> /etc/nginx/banned_ips.conf; nginx -t -q && systemctl reload nginx
actionunban = sed -i "/^<ip> 1;$/d" /etc/nginx/banned_ips.conf; nginx -t -q && systemctl reload nginx
EOF

# ---------- configuration nginx ----------
cat > "$GEO_FILE" <<'EOF'
geo $banned_ip {
    default 0;
    include /etc/nginx/banned_ips.conf;
}
EOF

# Ne jamais écraser la liste existante (elle contient les bans en cours)
if [[ ! -f "$BANNED_LIST" ]]; then
    touch "$BANNED_LIST"
fi
chmod 644 "$BANNED_LIST"

cat > "$SNIPPET" <<'EOF'
# fail2ban-banni : IP bannies par fail2ban (voir geo $banned_ip)
if ($banned_ip) {
    rewrite ^ /banni last;
}

location = /banni {
    default_type text/html;
    return 403 "<!doctype html><meta charset=utf-8><h1>Tu es banni</h1>";
}
EOF

# Include idempotent : on retire d'abord les includes précédents,
# puis on insère dans TOUS les blocs server
sed -i '\#^[[:space:]]*include .*fail2ban-banni#d' "$SITE_CONF"
tmp=$(mktemp)
awk -v inc="$INCLUDE_LINE" '
    /^[[:space:]]*server[[:space:]]*\{/ { print; print inc; next }
    { print }
' "$SITE_CONF" > "$tmp"
cat "$tmp" > "$SITE_CONF"
rm -f "$tmp"

if ! grep -q 'fail2ban-banni' "$SITE_CONF"; then
    echo "Aucun bloc server trouvé dans $SITE_CONF." >&2
    rollback
    exit 1
fi

nginx -t
systemctl reload nginx

# ---------- jail sans_pitie : banaction nginx ----------
# Remplace la ligne si elle existe, SINON l'insère juste après [sans_pitie]
tmp=$(mktemp)
awk '
    /^\[sans_pitie\][[:space:]]*$/ { print; print "banaction         = nginx-geo-ban"; s = 1; next }
    /^\[/ { s = 0 }
    s && /^banaction[[:space:]]*=/ { next }
    { print }
' "$JAIL_FILE" > "$tmp"
cat "$tmp" > "$JAIL_FILE"
rm -f "$tmp"

if ! awk '
    /^\[/ { s = ($0 == "[sans_pitie]") }
    s && /^banaction[[:space:]]*=[[:space:]]*nginx-geo-ban/ { f = 1 }
    END { exit !f }
' "$JAIL_FILE"; then
    echo "Ligne banaction introuvable dans [sans_pitie]." >&2
    rollback
    exit 1
fi

# ---------- redémarrage ----------
systemctl restart fail2ban
sleep 3
if ! systemctl is-active --quiet fail2ban; then
    echo "fail2ban n'a pas redémarré." >&2
    journalctl -u fail2ban -n 20 --no-pager >&2
    rollback
    exit 1
fi

trap - ERR
echo "Déploiement terminé."
fail2ban-client status sans_pitie
if nginx -T 2>/dev/null | grep -q 'fail2ban-banni'; then
    echo "Include nginx vérifié."
fi
