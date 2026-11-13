"""Chemins du projet et réglages lus dans gauchiasses.cfg. Aucun autre module n'écrit de chemin en dur."""
from __future__ import annotations

import configparser
from pathlib import Path

PAQUET = Path(__file__).resolve().parent  # gauchiasses/
ROOT = PAQUET.parent                      # racine du projet

CONFIG = ROOT / "gauchiasses.cfg"

# Sources (écrites à la main)
SOURCES = ROOT / "sources"
FLUX_RSS = SOURCES / "RSS_feeds.txt"
CHAINES_TWITCH = SOURCES / "Twitch_feeds.txt"
REGLAGES_FLUX = SOURCES / "flux_corrige_main.txt"
PAGE_ACCUEIL = ROOT / "accueil" / "index.html"  # page principale : écrite à la main, contient le bloc immuable
LISTES = ROOT / "listes"                         # fichiers texte des cartes de la page principale
STATIC = ROOT / "static"  # favicon, icône, image de partage, polices : recopiés tels quels dans build/
DOSSIER_IMAGES_CARTES = "img/cartes"  # images locales des cartes : static/img/cartes/, donc img/cartes/ sur le site

# Données (jamais publiées)
DATA = ROOT / "data"
HISTORIQUE_DB = DATA / "historique.db"
EMPREINTE = DATA / "immuable.json"
CACHE_DIR = DATA / "cache"
VERROU = DATA / "build.lock"

# Site généré : tout ce qui est publié, et rien d'autre
BUILD = ROOT / "build"
NOM_ACCUEIL = "index.html"   # page principale
NOM_VEILLE = "veille.html"   # le KiosKe
DOSSIER_IMAGES = "img/veille"  # images des articles, relatif à build/ et à la racine web
DOSSIER_RSS_CATEGORIES = "rss"  # un flux par catégorie : rss/<nom>.xml


def lire_config(chemin: Path = CONFIG) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if not cfg.read(chemin, encoding="utf-8"):
        raise SystemExit(f"fichier de réglages introuvable : {chemin}")
    return cfg


CFG = lire_config()


def valeur(section: str, cle: str) -> str:
    """Valeur obligatoire de gauchiasses.cfg. S'arrête avec un message clair si elle manque."""
    texte = CFG.get(section, cle, fallback="").strip()
    if not texte:
        raise SystemExit(f"{CONFIG.name} : la clé « {cle} » manque dans la section [{section}]")
    return texte


def entier(section: str, cle: str) -> int:
    texte = valeur(section, cle)
    if not texte.isdigit():
        raise SystemExit(f"{CONFIG.name} : [{section}] {cle} = « {texte} » : nombre entier positif attendu")
    return int(texte)


DOMAINE = valeur("site", "domaine")
URL_SITE = f"https://{DOMAINE}"
NOM_SITE = valeur("site", "nom")
RACINE_WEB = Path(valeur("serveur", "racine_web"))

NOM_KIOSKE = valeur("veille", "nom")
SLOGAN = valeur("veille", "slogan")
THEME_DEFAUT = valeur("veille", "theme")
RSS_MAX = entier("veille", "articles_flux_rss")
TWITCH_SCAN = entier("veille", "videos_par_chaine")
ARTICLES_PAR_SOURCE = entier("veille", "articles_par_source")  # 0 = tous
DELAI_ECHEC = entier("veille", "delai_nouvel_essai_heures") * 3600  # secondes

PERIODE_ETIQUETTES = valeur("cartes", "periode_etiquettes")  # secondes (contrôlée par gauchiasses/cartes.py)
POLICE = valeur("cartes", "police")
