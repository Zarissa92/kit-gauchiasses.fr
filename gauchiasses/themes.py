"""Thèmes du KiosKe (veille.html), décrits dans gauchiasses.cfg (sections [theme.<nom>]).

Le visiteur choisit son thème avec des boutons radio cachés : CSS seul, sans JavaScript ni cookie.
Le CSS de base est dans gauchiasses/style.css, celui de la pluie dans gauchiasses/pluie.css.
"""
from __future__ import annotations

import configparser
import random

from .config import CFG, CONFIG, PAQUET, THEME_DEFAUT
from .texte import esc

CSS = (PAQUET / "style.css").read_text(encoding="utf-8")        # contient les marqueurs __FOND__ et __PANNEAU__
CSS_PLUIE = (PAQUET / "pluie.css").read_text(encoding="utf-8")  # ajouté seulement si un thème a pluie = oui

# Valeur de --bg pour chaque fond possible (clé `fond` d'un thème).

FONDS = {
    "etoiles": """radial-gradient(1px 1px at 12% 18%, #fff 50%, transparent 51%),
    radial-gradient(1px 1px at 47% 63%, #ddd 50%, transparent 51%),
    radial-gradient(1.5px 1.5px at 81% 27%, #fff 50%, transparent 51%),
    radial-gradient(1px 1px at 64% 88%, #ccc 50%, transparent 51%),
    radial-gradient(1px 1px at 29% 45%, #eee 50%, transparent 51%),
    radial-gradient(1px 1px at 92% 71%, #fff 50%, transparent 51%),
    radial-gradient(1px 1px at 6% 82%, #bbb 50%, transparent 51%),
    radial-gradient(1.5px 1.5px at 38% 9%, #fff 50%, transparent 51%),
    radial-gradient(1px 1px at 73% 52%, #ddd 50%, transparent 51%),
    linear-gradient(-35deg, transparent 22%, rgba(200, 190, 255, .14) 38%, rgba(255, 245, 225, .30) 50%, rgba(200, 190, 255, .14) 62%, transparent 78%),
    #000""",
    "noir": "#000",
}


def fond_panneau(opacite: int) -> str:
    """Fond du grand panneau principal : noir (#0a0000) à l'opacité donnée en % (gauchiasses.cfg, opacite_panneau)."""
    return f"rgba(10, 0, 0, {opacite / 100:g})"


def charger_themes(cfg: configparser.ConfigParser = CFG) -> tuple[list[dict], str]:
    """Tous les thèmes de gauchiasses.cfg, et le thème par défaut (clé `theme` de [veille]).
    S'arrête avec un message clair si une valeur manque ou est invalide."""
    chemin = CONFIG
    defaut = cfg.get("veille", "theme", fallback=THEME_DEFAUT)
    themes = []
    for section in cfg.sections():
        if not section.startswith("theme."):
            continue
        ident = section.removeprefix("theme.")
        try:
            theme = {k: cfg.get(section, k) for k in ("nom", "fond", "pluie", "opacite_panneau")}
        except configparser.Error as exc:
            raise SystemExit(f"thème « {ident} » incomplet dans {chemin.name} : {exc}")
        if theme["fond"] not in FONDS:
            raise SystemExit(f"fond « {theme['fond']} » inconnu dans {ident} (valeurs : {', '.join(FONDS)})")
        try:
            opacite = int(theme["opacite_panneau"])
        except ValueError:
            raise SystemExit(f"opacite_panneau « {theme['opacite_panneau']} » dans {ident} : nombre entier attendu (0 à 100)")
        if not 0 <= opacite <= 100:
            raise SystemExit(f"opacite_panneau {opacite} dans {ident} : valeur entre 0 et 100 attendue")
        theme["opacite_panneau"] = opacite
        if theme["pluie"] not in ("oui", "non"):
            raise SystemExit(f"pluie « {theme['pluie']} » dans {ident} : valeur attendue oui ou non")
        theme["pluie"] = theme["pluie"] == "oui"
        theme["id"] = ident
        themes.append(theme)
    ids = [t["id"] for t in themes]
    if not themes:
        raise SystemExit(f"aucun thème dans {chemin.name} (sections [theme.<nom>])")
    if defaut not in ids:
        raise SystemExit(f"thème par défaut « {defaut} » absent de {chemin.name} (disponibles : {', '.join(ids)})")
    return themes, defaut


def css_des_themes(themes: list[dict], defaut: str) -> str:
    """CSS de la page : le thème par défaut dans :root, puis une règle par thème, activée par son bouton radio coché.
    Sans :has() (vieux navigateurs), seul le thème par défaut s'affiche."""
    d = next(t for t in themes if t["id"] == defaut)
    css = CSS.replace("__FOND__", FONDS[d["fond"]]).replace("__PANNEAU__", fond_panneau(d["opacite_panneau"]))
    regles = []
    for t in themes:
        cible = f":root:has(#theme-{t['id']}:checked)"
        regles.append(f"{cible} {{ --bg: {FONDS[t['fond']]}; --panneau-fond: {fond_panneau(t['opacite_panneau'])}; }}")
    if any(t["pluie"] for t in themes):
        css += CSS_PLUIE
        regles.append(f"#pluie {{ display: {'block' if d['pluie'] else 'none'}; }}")
        for t in themes:
            regles.append(f":root:has(#theme-{t['id']}:checked) #pluie {{ display: {'block' if t['pluie'] else 'none'}; }}")
    return css + "\n" + "\n".join(regles) + "\n"


def choix_theme_html(themes: list[dict], defaut: str) -> str:
    """Boutons radio cachés et étiquettes cliquables : le visiteur choisit le thème sans JavaScript.
    Avec un seul thème, il n'y a rien à choisir : aucun bouton."""
    if len(themes) < 2:
        return ""
    boutons = "".join(
        f'<input type="radio" name="theme" id="theme-{t["id"]}" class="theme-input"'
        f'{" checked" if t["id"] == defaut else ""}>'
        f'<label for="theme-{t["id"]}">{esc(t["nom"])}</label>'
        for t in themes
    )
    return f'<div class="choix-theme" role="radiogroup" aria-label="Thème du site">{boutons}</div>'


def rain(seed: int = 42, colonnes: int = 40) -> str:
    """Colonnes de pluie rouge, générées une fois (page statique, même rendu à chaque build). Thème « pluie »."""
    rnd = random.Random(seed)
    chars = "アイウエオカキクケコサシスセソタチツテトナニヌネノ0123456789ABCDEFXYZ*+-=<>"
    parts = []
    for k in range(colonnes):
        left = round(k * 100 / colonnes + rnd.uniform(-0.8, 0.8), 2)
        duree = round(rnd.uniform(3.6, 9.6), 1)
        retard = round(-rnd.uniform(0, 16), 1)
        texte = "\n".join(rnd.choice(chars) for _ in range(rnd.randint(14, 30)))
        parts.append(f'<i style="left:{left}%;animation-duration:{duree}s;animation-delay:{retard}s">{esc(texte)}</i>')
    return '<div id="pluie" aria-hidden="true">' + "".join(parts) + "</div>"
