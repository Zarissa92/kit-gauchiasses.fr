# lib_config.sh — lecture de gauchiasses.cfg pour les scripts de deploy/. À charger avec « source », pas à lancer.
# Le fichier appelant doit avoir défini DOSSIER (racine du projet).
#
#   cfg <section> <clé>   affiche la valeur ; s'arrête si elle manque.
# Exemple : DOMAINE="$(cfg site domaine)"

CONFIG_PROJET="$DOSSIER/gauchiasses.cfg"

cfg() {
    local section="$1" cle="$2" valeur
    [[ -f "$CONFIG_PROJET" ]] || { echo "[erreur] $CONFIG_PROJET introuvable" >&2; exit 1; }
    valeur="$(awk -v section="[$section]" -v cle="$cle" '
        /^[[:space:]]*\[/ { dans = ($0 == section); next }
        dans && /^[[:space:]]*[^#;[:space:]][^=]*=/ {
            nom = $0; sub(/[[:space:]]*=.*/, "", nom); sub(/^[[:space:]]+/, "", nom)
            if (nom == cle) { sub(/^[^=]*=[[:space:]]*/, ""); sub(/[[:space:]]+$/, ""); print; exit }
        }' "$CONFIG_PROJET")"
    [[ -n "$valeur" ]] || { echo "[erreur] gauchiasses.cfg : clé « $cle » absente de la section [$section]" >&2; exit 1; }
    printf '%s\n' "$valeur"
}
