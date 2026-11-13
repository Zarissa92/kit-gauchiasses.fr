"""Cartes de la page principale : nuage de catégories, fenêtres et cartes Wikipédia de accueil/index.html.

Tourne sur le PC, jamais sur le serveur (il interroge Wikipédia et garde ses caches dans data/cache/).
Le serveur reçoit accueil/index.html déjà construit et le recopie tel quel dans build/.

Format des fichiers texte : des blocs séparés par une ligne vide. Les lignes qui commencent par # sont ignorées.

    2📱Android (78)              <- titre de catégorie (bloc d'une seule ligne : chiffre, titre, (nombre))

    **Aya Nakamura**             <- carte : nom en gras sur la première ligne
    chanteuse franco malienne    <- description (utilisée si Wikipédia n'a pas d'extrait)
    image: photos/aya.jpg        <- image facultative, remplace l'image de Wikipédia. Formes acceptées :
                                    chemin local (copié dans static/img/cartes/, crédit « fournie dans le fichier texte »),
                                    Fichier:Nom.gif, File:Nom.jpg, ou le lien vers la page du fichier
                                    (https://fr.wikipedia.org/wiki/Fichier:... ou https://commons.wikimedia.org/wiki/File:...),
                                    qui donnent l'auteur et la licence du fichier

Règles appliquées à chaque carte :
- Le nom doit correspondre à une page existante de fr.wikipedia.org. Les pages absentes et
  les pages d'homonymie sont exclues.
- Une même page n'apparaît qu'une fois : la première occurrence est gardée.
- La carte est coupée en deux : l'image principale de l'article en haut, l'extrait en bas.
- Sous la carte : l'auteur et la licence de l'image, la licence du texte, et un lien vers l'article.

Nuage et fenêtres :
- une puce par catégorie qui a encore des cartes, avec le nombre de cartes (×N) ;
- cliquer sur une puce ouvre une fenêtre avec les cartes de la catégorie ;
- la fenêtre se ferme avec la croix ou en cliquant à l'extérieur (popover HTML, sans JavaScript) ;
- tous les réglages sont des variables CSS dans le bloc <style> généré (voir la liste plus bas).

Caches : data/cache/cache_wikipedia.json (pages et extraits) et data/cache/cache_images.json (auteurs
et licences). Un rapport des cartes exclues est écrit dans data/cache/rapport_cartes.txt.

Marqueurs écrits dans accueil/index.html :
- NUAGE-TAGS : le style et le nuage, juste avant le bloc immuable (hors de la zone protégée) ;
- CARTES-TEXTE : les fenêtres, après le bloc immuable.
Le bloc immuable n'est jamais modifié : verifier_zone() est appelé avant et après l'écriture.

Usage (voir bin/construire_cartes.py) :
    construire_cartes.py                      # toutes les listes de listes/*.txt
    construire_cartes.py listes/Vipex.txt     # seulement ces fichiers
    construire_cartes.py --hors-ligne         # n'interroge pas Wikipédia : utilise seulement les caches
    construire_cartes.py --periode=SECONDES   # période du passage au rouge des puces (défaut : gauchiasses.cfg)
    construire_cartes.py --police="Nom"       # police des titres (défaut : gauchiasses.cfg)
"""
from __future__ import annotations

import argparse

import filecmp
import itertools
import html
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, unquote, urlencode

from .config import (CACHE_DIR, DOSSIER_IMAGES_CARTES, LISTES, PAGE_ACCUEIL, PERIODE_ETIQUETTES, POLICE, ROOT,
                     STATIC)
from .construction import ecrire_accueil
from .immuable import verifier_zone
from .verrou import verrou

PAGE = PAGE_ACCUEIL                  # page principale, écrite à la main ; ce build n'en remplit que deux zones
IMG = STATIC / DOSSIER_IMAGES_CARTES  # images locales des cartes : publiées avec le reste de static/
CACHE = CACHE_DIR / "cache_wikipedia.json"
CACHE_IMAGES = CACHE_DIR / "cache_images.json"
RAPPORT = CACHE_DIR / "rapport_cartes.txt"
DEBUT = "<!-- CARTES-TEXTE:DEBUT -->"
FIN = "<!-- CARTES-TEXTE:FIN -->"
DEBUT_NUAGE = "<!-- NUAGE-TAGS:DEBUT -->"
FIN_NUAGE = "<!-- NUAGE-TAGS:FIN -->"
DEBUT_IMMUABLE = "<!-- IMMUABLE:DEBUT"
ANCRE = re.compile(r'<section class="cartes" aria-label="Cartes">\s*<div class="grille">')
TITRE_CATEGORIE = re.compile(r"(?:\d+\s*)?(.+?)\s*\(\d+\)")  # chiffre de tête facultatif
API = "https://fr.wikipedia.org/w/api.php"
UA = "gauchiasses/construire_cartes (build local)"
VERSION_CACHE = 5  # entrées du cache sans cette version sont redemandées (5 : repli sur logo = de l'infobox)
VERSION_FICHIERS = 4  # cache des fichiers image : inclut l'URL du fichier
TAILLE_LOT = 50    # titres par requête (limite de l'API pour un client normal)
PAUSE = 1.0        # secondes entre deux requêtes
LICENCE_TEXTE = ("https://creativecommons.org/licenses/by-sa/4.0/deed.fr", "CC BY-SA 4.0")


def style_html(periode: str, police: str) -> str:
    """Réglages (variables CSS) et règles du nuage, des fenêtres et des cartes."""
    fichier_police = police.lower().replace(" ", "-")  # « Russo One » -> fonts/russo-one.woff2
    return f"""<style>
@font-face{{font-family:"{police}";font-style:normal;font-weight:400;font-display:swap;src:url("fonts/{fichier_police}.woff2") format("woff2")}}
/* ===== RÉGLAGES : modifiez les valeurs ici (ou avec --periode au build) ===== */
:root {{
  --periode: {periode};              /* période du passage au rouge des puces */
  --rouge: #ff1a1a;                  /* couleur du passage au rouge (puces et cadres) */
  --police-titre: "{police}", "Courier New", monospace;  /* titres : h1, cartes, puces, fenêtres */
  --puce-taille: .8rem;              /* taille du texte des puces */
  --fenetre-fond: #0a0000;           /* fond opaque de la fenêtre */
  --fenetre-largeur: min(1100px, calc(100vw - 2rem));
  --fenetre-hauteur: calc(100vh - 2rem);
  --fond-voile: rgba(0, 0, 0, .8);   /* voile derrière la fenêtre */
  --carte-min: 210px;                /* largeur minimale d'une carte */
  --carte-ratio: .65;                /* largeur / hauteur d'une carte */
  --cadre-periode: 3s;               /* période du pulsement rouge du cadre */
  --carte-image-part: 50%;           /* part de la carte occupée par l'image */
  --carte-lignes: 6;                 /* nombre de lignes de l'extrait affichées */
}}
/* ===== POLICE UNIFORME : tout le site, y compris les déclarations « Courier New » existantes ===== */
html,body,body *{{font-family:var(--police-titre) !important}}
/* ===== NUAGE ===== */
.panel{{display:flex;flex-direction:column}}
.panel > .nuage{{order:1}}
.panel > .cagnotte{{order:2}}
.panel > .points{{width:100%;box-sizing:border-box}}
.nuage{{position:relative;background:#0a0000;border:1px solid #fff;box-shadow:0 0 18px rgba(255,255,255,.25);padding:.7rem;margin:1.2rem 0 0;display:flex;flex-wrap:wrap;justify-content:center;gap:.4rem}}
.nuage .tag{{display:inline-flex;align-items:center;gap:.35rem;padding:.2rem .55rem;border:1px solid #fff;border-radius:.3rem;background:none;color:#fff;font:inherit;font-size:var(--puce-taille);line-height:1.4;text-shadow:0 0 6px #fff;white-space:nowrap;cursor:pointer}}
.nuage .tag .nb{{font-size:.72rem;opacity:.75;text-shadow:none}}
.nuage .tag:hover,.nuage .tag:focus-visible{{color:#000;background:#fff;text-shadow:none;outline:none}}
.nuage .tag{{animation:tagRouge var(--periode) linear infinite}}
@keyframes tagRouge{{0%,100%{{color:#fff;border-color:#fff;text-shadow:0 0 6px #fff}}3%,12%{{color:var(--rouge);border-color:var(--rouge);text-shadow:0 0 6px var(--rouge)}}15%{{color:#fff;border-color:#fff;text-shadow:0 0 6px #fff}}}}
@media (prefers-reduced-motion: reduce){{.nuage .tag{{animation:none}}}}
/* ===== FENÊTRE (popover) ===== */
.fenetre{{position:fixed;inset:0;margin:auto;width:var(--fenetre-largeur);height:fit-content;max-height:var(--fenetre-hauteur);overflow:auto;box-sizing:border-box;padding:1.2rem;background:var(--fenetre-fond);color:#fff;border:1px solid var(--rouge);box-shadow:0 0 30px color-mix(in srgb, var(--rouge) 35%, transparent)}}
.fenetre::backdrop{{background:var(--fond-voile)}}
.fenetre-titre{{margin:0 2.6rem 1rem 0;font-size:1.2rem;line-height:1.3;text-transform:uppercase;text-shadow:0 0 8px #fff}}
.fenetre-fermer{{position:absolute;top:.5rem;right:.5rem;width:2rem;height:2rem;border:1px solid #fff;background:#000;color:#fff;font:inherit;font-size:1.2rem;cursor:pointer}}
.fenetre-fermer:hover,.fenetre-fermer:focus-visible{{background:#fff;color:#000}}
.fenetre-grille{{display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--carte-min),1fr));gap:1rem}}
/* ===== CARTE : image en haut, texte en bas, crédits dessous ===== */
.carte-bloc{{display:flex;flex-direction:column;gap:.35rem;min-width:0}}
.carte,.points .carte{{display:flex;flex-direction:column;aspect-ratio:var(--carte-ratio);height:auto;background:#080000;border:1px solid var(--rouge);overflow:hidden;animation:cadreRouge var(--cadre-periode) ease-in-out infinite}}
@keyframes cadreRouge{{0%,100%{{border-color:var(--rouge);box-shadow:0 0 6px var(--rouge)}}50%{{border-color:color-mix(in srgb, var(--rouge) 25%, #000);box-shadow:0 0 14px var(--rouge)}}}}
@media (prefers-reduced-motion: reduce){{.carte,.points .carte{{animation:none}}}}
.carte-image,.points .carte-image{{flex:0 0 var(--carte-image-part);display:flex;align-items:center;justify-content:center;background:#140000;border-bottom:1px solid var(--rouge);font:700 2.4rem "Courier New",monospace;color:#fff;text-shadow:0 0 6px #fff;overflow:hidden}}
.carte-image img,.points .carte-image img{{width:100%;height:100%;object-fit:contain;display:block}}
.carte-texte,.points .carte-corps{{flex:1;min-height:0;padding:.6rem .7rem;display:flex;flex-direction:column;gap:.4rem;overflow:hidden}}
.carte h3{{margin:0;font-size:.9rem;line-height:1.2;text-transform:uppercase;text-shadow:0 0 6px #fff;overflow-wrap:anywhere}}
.carte p{{margin:0;font-size:.78rem;line-height:1.35;display:-webkit-box;-webkit-line-clamp:var(--carte-lignes);-webkit-box-orient:vertical;overflow:hidden}}
.carte-wiki{{margin-top:auto;font-size:.7rem;color:#fff}}
.carte-credit{{margin:0;font-size:.7rem;line-height:1.4;opacity:.85;overflow-wrap:anywhere}}
.carte-credit a{{color:#fff}}
/* lisibilité : pas de halo lumineux sur les textes courants (les titres principaux gardent leur effet) */
.carte h3,.carte p,.carte-credit,.carte-wiki,.fiche-carte-titre,.fiche-carte-texte,.fiche-carte-licence,.fenetre-titre,.conduite h2,.conduite h3,.fiche h2{{text-shadow:none}}
.carte{{position:relative}}
.carte-plus{{position:absolute;right:.45rem;bottom:.45rem;width:1.8rem;height:1.8rem;display:flex;align-items:center;justify-content:center;border:1px solid var(--rouge);background:#000;color:#fff;font:inherit;font-size:1.1rem;cursor:pointer;z-index:2}}
.carte-plus:hover,.carte-plus:focus-visible{{background:var(--rouge);color:#000}}
.carte-credit{{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
.fiche-carte{{position:fixed;inset:0;margin:auto;width:min(760px,calc(100vw - 2rem));height:fit-content;max-height:var(--fenetre-hauteur);overflow:auto;box-sizing:border-box;padding:1.2rem;background:var(--fenetre-fond);color:#fff;border:1px solid var(--rouge);box-shadow:0 0 30px color-mix(in srgb, var(--rouge) 35%, transparent)}}
.fiche-carte::backdrop{{background:var(--fond-voile)}}
.fiche-carte-titre{{margin:0 2.6rem .8rem 0;font-size:1.2rem;line-height:1.3;text-transform:uppercase;text-shadow:0 0 8px #fff}}
.fiche-carte-image{{display:block;max-width:100%;max-height:45vh;margin:0 auto .8rem;object-fit:contain;border:1px solid var(--rouge)}}
.fiche-carte-lettre{{font-size:4rem;font-weight:700;text-align:center;margin-bottom:.8rem}}
.fiche-carte-texte{{margin:0 0 1rem;line-height:1.5}}
.fiche-carte-licence{{margin:0;font-size:.82rem;line-height:1.5}}
.fiche-carte-licence dt{{color:var(--rouge);text-transform:uppercase;margin-top:.6rem}}
.fiche-carte-licence dd{{margin:.1rem 0 0 0;overflow-wrap:anywhere}}
.fiche-carte-licence a{{color:#fff}}
</style>"""


COMPTE_COPIE = re.compile(r"\d+\s*cartes?")  # ligne « 19 cartes » (format copié-collé)
RARETES = ("Commune", "Rare", "Inhabituelle", "Épique", "Exceptionnelle", "Légendaire", "Mythique")  # lignes ignorées dans le format copié-collé


EMOJI_FIN = re.compile(r"^(.*?)\s*((?:[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2190-\u21FF"
                        r"\u2300-\u23FF\u00A9\u00AE\u2122\u2139\u3030\u303D\u3297\u3299\uFE0F\u200D])+)$")


def titre_copie(titre: str) -> str:
    """Titre du format copié-collé : un emoji en fin de titre passe en tête, comme dans le format wikipick
    (« Vipex🚩 » devient « 🚩Vipex »)."""
    m = EMOJI_FIN.fullmatch(titre)
    return f"{m.group(2)}{m.group(1)}" if m and m.group(1) else titre


def _suivant(lignes, i):
    """Index de la prochaine ligne non vide à partir de i (len(lignes) si aucune)."""
    while i < len(lignes) and not lignes[i].strip():
        i += 1
    return i


def _est_entete_copie(lignes, i):
    """Vrai si la ligne i est un titre suivi de « N cartes » : format copié-collé."""
    j = _suivant(lignes, i + 1)
    return bool(lignes[i].strip()) and j < len(lignes) and COMPTE_COPIE.fullmatch(lignes[j].strip()) is not None


def lire_fichier(chemin: Path):
    """Retourne une liste d'éléments : ('categorie', titre) ou ('carte', nom, description, image, dossier).

    Deux formats, mélangeables dans un même fichier :
    - wikipick : titre « 5🚩Vipex (19) » seul sur sa ligne ; carte « **Nom** », description, image: facultatif ;
      les blocs sont séparés par une ligne vide.
    - copié-collé : titre suivi de « 19 cartes », puis pour chaque carte le nom, la description, et
      éventuellement une rareté (Mythique, Légendaire, Exceptionnelle, Épique), ignorée.
    """
    lignes = [l.rstrip() for l in chemin.read_text(encoding="utf-8").splitlines() if not l.startswith("#")]
    dossier = chemin.parent
    elements = []
    i = 0
    while True:
        i = _suivant(lignes, i)
        if i >= len(lignes):
            break
        l = lignes[i].strip()
        if _est_entete_copie(lignes, i):
            elements.append(("categorie", titre_copie(l)))
            i = _suivant(lignes, i + 1) + 1  # saute le titre et la ligne « N cartes »
            while True:
                i = _suivant(lignes, i)
                if i >= len(lignes):
                    break
                s = lignes[i].strip()
                if s in RARETES:  # rareté isolée : ignorée
                    i += 1
                    continue
                if _est_entete_copie(lignes, i) or TITRE_CATEGORIE.fullmatch(s) or s.startswith("**"):
                    break
                nom = s
                j = _suivant(lignes, i + 1)
                desc = lignes[j].strip() if j < len(lignes) else ""
                i = j + 1
                k = _suivant(lignes, i)
                if k < len(lignes) and lignes[k].strip() in RARETES:
                    i = k + 1
                elements.append(("carte", nom, desc, None, dossier))
            continue
        if TITRE_CATEGORIE.fullmatch(l):
            elements.append(("categorie", TITRE_CATEGORIE.fullmatch(l).group(1)))
            i += 1
            continue
        nom = re.fullmatch(r"\*\*(.+?)\*\*", l)
        if not nom:
            raise SystemExit(f"{chemin} ligne {i + 1} : format non reconnu : {l!r}")
        i += 1
        image = None
        description = []
        while i < len(lignes):
            s = lignes[i].strip()
            if not s or s.startswith("**") or _est_entete_copie(lignes, i):
                break
            if s.lower().startswith("image:"):
                image = s[len("image:"):].strip()
            else:
                description.append(s)
            i += 1
        elements.append(("carte", nom.group(1).strip(), " ".join(description), image, dossier))
    return elements


FICHIER_WIKIMEDIA = re.compile(
    r"^(?:https?://(?:fr\.wikipedia\.org/wiki|commons\.wikimedia\.org/wiki)/)?(?:Fichier|File):(.+)$"
)


def fichier_reference(valeur: str):
    """Nom du fichier Wikimédia désigné par une valeur « image: » : Fichier:X, File:X, ou lien vers
    la page du fichier (fr.wikipedia.org ou commons.wikimedia.org). Renvoie None sinon (chemin local,
    URL d'image directe)."""
    m = FICHIER_WIKIMEDIA.match(valeur.strip())
    if not m:
        return None
    nom = unquote(m.group(1)).split("?")[0].split("#")[0].strip().replace(" ", "_")
    return nom or None


def charger_json(chemin: Path):
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def sauver_json(chemin: Path, donnees):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def texte_nettoye(valeur: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", valeur or "")).strip()


def avec_reessais(fonction, lot, essais=6):
    """Appelle fonction(lot) en réessayant sur 429 ou 503, en attendant Retry-After si fourni."""
    attente = 30
    for tentative in range(1, essais + 1):
        try:
            return fonction(lot)
        except urllib.error.HTTPError as erreur:
            if erreur.code not in (429, 503) or tentative == essais:
                raise SystemExit(f"Wikipédia a répondu HTTP {erreur.code} : relancez plus tard, les caches sont conservés")
            retry_after = erreur.headers.get("Retry-After")
            delai = int(retry_after) if retry_after and retry_after.isdigit() else attente
            print(f"  HTTP {erreur.code} : pause de {delai} s avant de réessayer")
            time.sleep(delai)
            attente *= 2


def requete_api(parametres):
    url = API + "?" + urlencode({"action": "query", "format": "json", "formatversion": "2", **parametres})
    requete = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        return json.load(reponse)["query"]


PARAM_IMAGE_INFOBOX = re.compile(r"\|\s*image\s*=\s*([^\n|}]+)")
PARAM_LOGO_INFOBOX = re.compile(r"\|\s*logo\s*=\s*([^\n|}]+)")  # repli : certaines infobox de médias


def interroger_infobox(titres_pages):
    """Image déclarée dans l'infobox de l'article (paramètre « image = »).
    Sert de repli quand Wikipédia ne donne pas d'image principale. Renvoie {page: nom de fichier}."""
    donnees = requete_api({
        "prop": "revisions", "rvprop": "content", "rvslots": "main",
        "titles": "|".join(titres_pages),
    })
    trouvees = {}
    for page in donnees.get("pages", []):
        revisions = page.get("revisions") or [{}]
        principal = (revisions[0].get("slots") or {}).get("main") or {}
        texte = principal.get("content") or principal.get("*") or ""
        m = PARAM_IMAGE_INFOBOX.search(texte) or PARAM_LOGO_INFOBOX.search(texte)
        if not m:
            continue
        nom = m.group(1).strip()
        nom = re.sub(r"^\[\[|\]\]$", "", nom).strip().strip("\"'").strip()
        nom = re.sub(r"^(?:Fichier|File|Image):", "", nom).strip()
        if nom and nom != "-" and "{" not in nom:
            trouvees[page["title"]] = nom
    return trouvees


def interroger_pages(titres):
    """Résout un lot de noms : page, homonymie, extrait et image principale de l'article."""
    donnees = requete_api({
        "redirects": "1", "prop": "pageprops|extracts|pageimages", "ppprop": "disambiguation",
        "exintro": "1", "explaintext": "1", "exsentences": "10",
        "piprop": "thumbnail|name", "pithumbsize": "480",
        "titles": "|".join(titres),
    })
    normalises = {n["from"]: n["to"] for n in donnees.get("normalized", [])}
    redirections = {r["from"]: r["to"] for r in donnees.get("redirects", [])}
    pages = {p["title"]: p for p in donnees["pages"]}
    # Repli : l'infobox, seulement pour les articles sans image principale
    sans_image = [
        p["title"] for p in donnees["pages"]
        if not (p.get("missing") or p.get("invalid") or "disambiguation" in p.get("pageprops", {})
                or p.get("pageimage"))
    ]
    infobox = {}
    for i in range(0, len(sans_image), 10):
        infobox.update(interroger_infobox(sans_image[i:i + 10]))
    resultat = {}
    for titre in titres:
        cible = redirections.get(normalises.get(titre, titre), normalises.get(titre, titre))
        page = pages.get(cible)
        base = {"v": VERSION_CACHE, "page": None, "motif": "page absente", "extrait": None,
                "image_url": None, "image_fichier": None}
        if page is None or page.get("missing") or page.get("invalid"):
            resultat[titre] = base
        elif "disambiguation" in page.get("pageprops", {}):
            resultat[titre] = {**base, "page": page["title"], "motif": "page d'homonymie"}
        else:
            extrait = re.sub(r"\s+", " ", page.get("extract") or "").strip()
            resultat[titre] = {
                **base,
                "page": page["title"], "motif": None,
                "extrait": extrait or None,
                "image_url": (page.get("thumbnail") or {}).get("source"),
                "image_fichier": page.get("pageimage") or infobox.get(page["title"]),
            }
    return resultat


CHAMPS_LICENCE = ("Artist", "Credit", "Attribution", "AttributionRequired",
                  "LicenseShortName", "UsageTerms", "LicenseUrl", "Permission")


def interroger_fichiers(fichiers):
    """Métadonnées de licence des fichiers image (Wikimedia Commons), champ par champ."""
    donnees = requete_api({
        "prop": "imageinfo", "iiprop": "url|extmetadata",
        "iiextmetadatafilter": "|".join(CHAMPS_LICENCE),
        "titles": "|".join("File:" + f for f in fichiers),
    })
    normalises = {n["from"]: n["to"] for n in donnees.get("normalized", [])}
    pages = {p["title"]: p for p in donnees.get("pages", [])}
    resultat = {}
    for f in fichiers:
        cle = normalises.get("File:" + f, "File:" + f)
        page = pages.get(cle, {})
        ii = (page.get("imageinfo") or [{}])[0]
        brut = ii.get("extmetadata", {})
        meta = {}
        for champ in CHAMPS_LICENCE:
            valeur = texte_nettoye(brut.get(champ, {}).get("value", ""))
            if valeur:
                meta[champ] = valeur
        resultat[f] = {
            "v": VERSION_FICHIERS,
            "url": (ii.get("url") or "").split("?")[0],
            "auteur": meta.get("Artist", ""),
            "licence": meta.get("LicenseShortName", ""),
            "licence_url": meta.get("LicenseUrl", ""),
            "meta": meta,
        }
    return resultat


def resoudre(titres, hors_ligne: bool):
    cache = charger_json(CACHE)
    a_interroger = [t for t in titres if cache.get(t, {}).get("v") != VERSION_CACHE]
    if a_interroger and hors_ligne:
        print(f"{len(a_interroger)} nom(s) absent(s) du cache, refusés (--hors-ligne)", file=sys.stderr)
        for t in a_interroger:
            cache[t] = {"v": VERSION_CACHE, "page": None, "motif": "absent du cache",
                        "extrait": None, "image_url": None, "image_fichier": None}
    else:
        for i in range(0, len(a_interroger), TAILLE_LOT):
            lot = a_interroger[i:i + TAILLE_LOT]
            cache.update(avec_reessais(interroger_pages, lot))
            sauver_json(CACHE, cache)  # sauvegarde après chaque lot : reprise possible
            print(f"  pages Wikipédia : {min(i + TAILLE_LOT, len(a_interroger))}/{len(a_interroger)}")
            time.sleep(PAUSE)
    sauver_json(CACHE, cache)
    return {t: cache[t] for t in titres}


def resoudre_fichiers(fichiers, hors_ligne: bool):
    cache = charger_json(CACHE_IMAGES)
    a_interroger = sorted(f for f in fichiers if cache.get(f, {}).get("v") != VERSION_FICHIERS)
    if a_interroger and hors_ligne:
        for f in a_interroger:
            cache[f] = {"v": VERSION_FICHIERS, "url": "", "auteur": "", "licence": "", "licence_url": ""}
    else:
        for i in range(0, len(a_interroger), TAILLE_LOT):
            lot = a_interroger[i:i + TAILLE_LOT]
            cache.update(avec_reessais(interroger_fichiers, lot))
            sauver_json(CACHE_IMAGES, cache)
            print(f"  licences d'images : {min(i + TAILLE_LOT, len(a_interroger))}/{len(a_interroger)}")
            time.sleep(PAUSE)
    sauver_json(CACHE_IMAGES, cache)
    return {f: cache[f] for f in fichiers}


def image_locale(reference, dossier_texte: Path):
    """Copie une image donnée dans le fichier texte et renvoie son chemin pour la page."""
    if reference.startswith("https://"):
        return reference
    if reference.startswith("http://"):
        raise SystemExit(f"URL refusée (http, pas https) : {reference}")
    source = (dossier_texte / reference).resolve()
    if not source.is_file():
        raise SystemExit(f"image introuvable : {source}")
    IMG.mkdir(parents=True, exist_ok=True)
    cible = IMG / source.name
    if cible.exists() and not filecmp.cmp(source, cible, shallow=False):
        raise SystemExit(f"conflit de nom dans {IMG.relative_to(ROOT)}/ : {source.name} existe déjà avec un autre contenu")
    shutil.copy2(source, cible)
    return f"{DOSSIER_IMAGES_CARTES}/{source.name}"


def lien_wikipedia(page: str) -> str:
    return "https://fr.wikipedia.org/wiki/" + quote(page.replace(" ", "_"), safe="_()'!,:/-.")


ETIQUETTES_LICENCE = [
    ("Artist", "Auteur.ice"),
    ("Credit", "Crédit"),
    ("Attribution", "Attribution"),
    ("AttributionRequired", "Attribution requise"),
    ("LicenseShortName", "Licence"),
    ("UsageTerms", "Conditions d'utilisation"),
    ("LicenseUrl", "Lien de la licence"),
    ("Permission", "Permission"),
]


def court(texte: str, longueur: int = 40) -> str:
    return texte if len(texte) <= longueur else texte[:longueur - 1].rstrip() + "…"


def licence_affichee(texte: str) -> str:
    """Libellé de licence en français : « Public domain » devient « Domaine public »."""
    if texte.strip().lower().startswith("public domain"):
        return "Domaine public"
    return texte


def credit_court(image_source, fichier) -> str:
    """Ligne de crédit sous la carte : courte, le détail est dans la fiche."""
    lignes = []
    if image_source == "locale":
        lignes.append("Image : fournie dans le fichier texte")
    elif image_source == "wikipedia":
        auteur = court((fichier or {}).get("auteur") or "auteur.ice non précisé.e")
        licence = licence_affichee((fichier or {}).get("licence") or "licence non précisée")
        lignes.append(f"Image : {auteur} · {licence}")
    lignes.append(f"Texte : Wikipédia · {LICENCE_TEXTE[1]}")
    return '<p class="carte-credit">' + "<br>".join(html.escape(l) for l in lignes) + "</p>"


def fiche_html(ident, nom, description, info, image, image_source, fichier, page) -> str:
    """Panneau détaillé : extrait complet et toute la licence de l'image."""
    texte = info.get("extrait") or description
    meta = (fichier or {}).get("meta") or {}
    lignes = []
    if image_source == "locale":
        lignes.append("<dt>Image</dt><dd>fournie dans le fichier texte</dd>")
    elif image_source == "wikipedia" and not meta:
        lignes.append("<dt>Image</dt><dd>auteur.ice et licence non précisé.e.s</dd>")
    for cle, etiquette in ETIQUETTES_LICENCE:
        valeur = meta.get(cle)
        if not valeur:
            continue
        if cle == "LicenseUrl":
            v = f'<a href="{html.escape(valeur)}" target="_blank" rel="noopener">{html.escape(valeur)}</a>'
        else:
            if cle in ("LicenseShortName", "UsageTerms"):
                valeur = licence_affichee(valeur)
            v = html.escape(re.sub(r"\n\s*\n+", "\n", valeur)).replace("\n", "<br>")
        lignes.append(f"<dt>{etiquette}</dt><dd>{v}</dd>")
    lignes.append(f'<dt>Texte</dt><dd>Wikipédia, <a href="{LICENCE_TEXTE[0]}" target="_blank" rel="noopener">'
                  f'{LICENCE_TEXTE[1]}</a></dd>')
    lignes.append(f'<dt>Article</dt><dd><a href="{html.escape(lien_wikipedia(page))}" target="_blank" '
                  f'rel="noopener">Lire sur Wikipédia</a></dd>')
    if image:
        visuel = f'<img class="fiche-carte-image" src="{html.escape(image)}" alt="">'
    else:
        visuel = f'<div class="fiche-carte-lettre" aria-hidden="true">{html.escape(nom[:1].upper())}</div>'
    return (
        f'<div id="{ident}" class="fiche-carte" popover>'
        f'<button type="button" class="fenetre-fermer" popovertarget="{ident}" popovertargetaction="hide" '
        f'aria-label="Fermer">×</button>'
        f'<h3 class="fiche-carte-titre">{html.escape(nom)}</h3>'
        f'{visuel}'
        f'<p class="fiche-carte-texte">{html.escape(texte)}</p>'
        f'<dl class="fiche-carte-licence">{"".join(lignes)}</dl>'
        f'</div>'
    )


def carte_bloc(nom, description, info, image_source, image, fichier, page, ident) -> str:
    texte = info.get("extrait") or description
    if image:
        visuel = f'<img src="{html.escape(image)}" alt="" loading="lazy">'
    else:
        visuel = html.escape(nom[:1].upper())
    return (
        f'<div class="carte-bloc"><article class="carte">'
        f'<div class="carte-image" aria-hidden="true">{visuel}</div>'
        f'<div class="carte-texte"><h3>{html.escape(nom)}</h3>'
        f'<p>{html.escape(texte)}</p>'
        f'<a class="carte-wiki" href="{html.escape(lien_wikipedia(page))}" target="_blank" rel="noopener">Wikipédia →</a>'
        f'</div>'
        f'<button type="button" class="carte-plus" popovertarget="{ident}" '
        f'aria-label="Ouvrir la fiche : {html.escape(nom)}">+</button>'
        f'</article>{credit_court(image_source, fichier)}'
        f'{fiche_html(ident, nom, description, info, image, image_source, fichier, page)}'
        f'</div>'
    )


def fenetre_html(ident, titre, contenu) -> str:
    return (
        f'<div id="categorie-{ident}" class="fenetre" popover>'
        f'<button type="button" class="fenetre-fermer" popovertarget="categorie-{ident}" '
        f'popovertargetaction="hide" aria-label="Fermer">×</button>'
        f'<h2 class="fenetre-titre">{html.escape(titre)}</h2>'
        f'<div class="fenetre-grille">{contenu}</div></div>'
    )


def puce_html(titre, ident, n, i) -> str:
    decalage = (i * 0.618) % 1  # répartit les passages au rouge dans la période
    return (
        f'<button type="button" class="tag" popovertarget="categorie-{ident}" '
        f'style="animation-delay:calc(var(--periode) * -{decalage:.3f})">'
        f'{html.escape(titre)} <span class="nb">×{n}</span></button>'
    )


def groupes_par_categorie(elements):
    """Retourne [(titre ou None, [cartes])]. Les cartes sans catégorie viennent en premier."""
    groupes = [(None, [])]
    for el in elements:
        if el[0] == "categorie":
            groupes.append((el[1], []))
        else:
            groupes[-1][1].append(el)
    return [g for g in groupes if g[0] is not None or g[1]]


def analyser_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("fichiers", nargs="*", type=Path, metavar="FICHIER",
                        help="listes à lire (défaut : tous les fichiers de listes/*.txt)")
    parser.add_argument("--hors-ligne", action="store_true", help="n'interroge pas Wikipédia : utilise seulement les caches")
    parser.add_argument("--periode", default=PERIODE_ETIQUETTES, metavar="SECONDES",
                        help=f"période du passage au rouge des puces (défaut : {PERIODE_ETIQUETTES}, gauchiasses.cfg)")
    parser.add_argument("--police", default=POLICE, metavar="NOM",
                        help=f"police des titres (défaut : {POLICE}, gauchiasses.cfg)")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"\d+(\.\d+)?", args.periode) or float(args.periode) <= 0:
        raise SystemExit(f"période : nombre de secondes positif attendu : {args.periode!r}")
    args.police = args.police.strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ]*", args.police):
        raise SystemExit(f"police : nom de police attendu : {args.police!r}")
    fichier_police = STATIC / "fonts" / (args.police.lower().replace(" ", "-") + ".woff2")
    if not fichier_police.is_file():
        raise SystemExit(f"police « {args.police} » : fichier absent : {fichier_police.relative_to(ROOT)}")
    if not args.fichiers:
        args.fichiers = sorted(LISTES.glob("*.txt"))
    if not args.fichiers:
        raise SystemExit(f"aucune liste dans {LISTES.relative_to(ROOT)}/")
    return args


def main(argv: list[str] | None = None) -> int:
    args = analyser_arguments(argv)
    hors_ligne = args.hors_ligne
    periode = f"{args.periode}s"
    police = args.police

    elements = []
    for fichier in args.fichiers:
        elements += lire_fichier(fichier.resolve())

    groupes = groupes_par_categorie(elements)
    noms = sorted({el[1] for _, cartes in groupes for el in cartes})
    print(f"{len(noms)} nom(s) distinct(s) à vérifier")
    resultats = resoudre(noms, hors_ligne)
    # Fichiers image : ceux de Wikipédia, plus ceux désignés explicitement (image: Fichier:...)
    explicites = {
        fichier_reference(el[3])
        for _, cartes in groupes for el in cartes
        if el[3] and fichier_reference(el[3])
    }
    fichiers = sorted({r["image_fichier"] for r in resultats.values() if r.get("image_fichier")} | explicites)
    print(f"{len(fichiers)} image(s) de Wikipédia à créditer")
    infos_fichiers = resoudre_fichiers(fichiers, hors_ligne)

    compteur = itertools.count(1)
    vues = {}  # page Wikipédia -> (nom, catégorie) de la première occurrence
    absentes, homonymies, doublons = [], [], []
    non_categorisees = []
    fenetres = []
    puces = []
    nb_cartes = 0
    for titre, cartes in groupes:
        categorie = titre or "(sans catégorie)"
        rendus = []
        for el in cartes:
            _, nom, description, image_fichier_texte, dossier = el
            info = resultats[nom]
            if info["page"] is None:
                absentes.append((categorie, nom, info["motif"]))
                continue
            if info["motif"] == "page d'homonymie":
                homonymies.append((categorie, nom, info["page"]))
                continue
            page = info["page"]
            if page in vues:
                doublons.append((categorie, nom, page, vues[page]))
                continue
            vues[page] = (nom, categorie)
            nom_fichier = fichier_reference(image_fichier_texte) if image_fichier_texte else None
            if nom_fichier:
                source, image, fichier = "wikipedia", infos_fichiers[nom_fichier]["url"], infos_fichiers[nom_fichier]
            elif image_fichier_texte:
                source, image = "locale", image_locale(image_fichier_texte, dossier)
                fichier = None
            elif info.get("image_url"):
                source, image = "wikipedia", info["image_url"]
                fichier = infos_fichiers.get(info["image_fichier"])
            elif infos_fichiers.get(info.get("image_fichier") or "", {}).get("url"):
                # Image de l'infobox (pas de miniature Wikipédia) : fichier Commons directement
                fichier = infos_fichiers[info["image_fichier"]]
                source, image = "wikipedia", fichier["url"]
            else:
                source, image, fichier = None, None, None
            rendus.append(carte_bloc(nom, description, info, source, image, fichier, page, f"carte-{next(compteur)}"))
        if not rendus:
            continue
        nb_cartes += len(rendus)
        if titre is None:
            non_categorisees += rendus
        else:
            ident = len(puces) + 1
            puces.append((titre, ident, len(rendus)))
            fenetres.append(fenetre_html(ident, titre, "".join(rendus)))

    rapport = [f"Cartes écrites : {nb_cartes}", ""]
    rapport.append(f"Pages absentes de Wikipédia, exclues ({len(absentes)}) :")
    rapport += [f"  [{c}] {n}  ({m})" for c, n, m in absentes]
    rapport.append("")
    rapport.append(f"Pages d'homonymie, exclues ({len(homonymies)}) :")
    rapport += [f"  [{c}] {n}  -> {p}" for c, n, p in homonymies]
    rapport.append("")
    rapport.append(f"Doublons supprimés ({len(doublons)}) :")
    rapport += [f"  [{c}] {n}  -> même page que « {v[0]} » [{v[1]}] ({p})" for c, n, p, v in doublons]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RAPPORT.write_text("\n".join(rapport) + "\n", encoding="utf-8")

    with verrou():  # pas d'écriture pendant un build ou une publication
        ecrire_zones(non_categorisees, fenetres, puces, periode, police)
    print(f"{nb_cartes} carte(s) écrite(s) dans {PAGE.relative_to(ROOT)}")
    print(f"  nuage : {len(puces)} catégorie(s), période {periode}")
    print(f"  pages absentes : {len(absentes)} | homonymies : {len(homonymies)} | doublons : {len(doublons)}")
    print(f"  rapport : {RAPPORT.relative_to(ROOT)}")
    return 0


def ecrire_zones(non_categorisees, fenetres, puces, periode: str, police: str) -> None:
    """Remplit les deux zones générées de accueil/index.html (NUAGE-TAGS et CARTES-TEXTE), puis recopie
    la page dans build/. Le bloc immuable est contrôlé avant et après l'écriture."""
    page_html = PAGE.read_text(encoding="utf-8")
    verifier_zone(page_html)

    # Fenêtres et cartes : après le bloc immuable.
    corps = DEBUT + "\n" + "".join(non_categorisees) + "\n" + "\n".join(fenetres) + "\n" + FIN
    if DEBUT in page_html:
        page_html = re.sub(re.escape(DEBUT) + r".*?" + re.escape(FIN), lambda _: corps, page_html, flags=re.S)
    else:
        ancres = ANCRE.findall(page_html)
        if len(ancres) != 1:
            raise SystemExit("section « cartes » introuvable dans accueil/index.html")
        page_html = page_html.replace(ancres[0], ancres[0] + "\n" + corps, 1)

    # Style et nuage : juste avant le bloc immuable (hors de la zone protégée).
    nuage = (
        DEBUT_NUAGE + "\n" + style_html(periode, police) + "\n"
        + '<section class="nuage" aria-label="Catégories">\n'
        + "\n".join(puce_html(t, i, n, k) for k, (t, i, n) in enumerate(puces))
        + "\n</section>\n" + FIN_NUAGE
    )
    if DEBUT_NUAGE in page_html:
        page_html = re.sub(re.escape(DEBUT_NUAGE) + r".*?" + re.escape(FIN_NUAGE), lambda _: nuage, page_html, flags=re.S)
    else:
        if page_html.count(DEBUT_IMMUABLE) != 1:
            raise SystemExit("marqueur IMMUABLE absent ou en double")
        position = page_html.index(DEBUT_IMMUABLE)
        page_html = page_html[:position] + nuage + "\n" + page_html[position:]

    verifier_zone(page_html)
    tmp = PAGE.with_name(PAGE.name + ".tmp")
    tmp.write_text(page_html, encoding="utf-8")
    tmp.replace(PAGE)
    ecrire_accueil()  # build/index.html suit la source
