"""Construction du site dans build/ : page principale, KiosKe (veille.html), flux RSS, images, fichiers statiques.

Usage (voir bin/build_site.py) :
    build_site.py                 # build complet : flux, Twitch, aperçus, images, pages, flux RSS
    build_site.py --simple        # pages seules, sans réseau : articles de la base, caches existants
    build_site.py --no-twitch     # sans les chaînes Twitch
    build_site.py --no-previews   # sans visiter les pages (rapide)
    build_site.py --no-cache      # ignore les caches (aperçus et Twitch)
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import filecmp
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import apercus, immuable
from .config import (ARTICLES_PAR_SOURCE, BUILD, CHAINES_TWITCH, DOSSIER_RSS_CATEGORIES, FLUX_RSS, HISTORIQUE_DB,
                     NOM_ACCUEIL, NOM_KIOSKE, NOM_VEILLE, PAGE_ACCUEIL, REGLAGES_FLUX, ROOT, RSS_MAX, STATIC,
                     TWITCH_SCAN, URL_SITE)
from .flux import load_feed
from .historique import Historique
from .images import appliquer_images, purger_images, telecharger_images
from .rendu import render_page
from .rss import render_rss
from .sources import AUTRES, ordre_des_categories, read_categories, read_feeds, read_local, read_twitch
from .texte import slugs_categories
from .twitch import load_twitch
from .verrou import verrou


def analyser_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-rss", dest="rss", type=Path, default=FLUX_RSS, metavar="FICHIER",
                        help="fichier des flux RSS (défaut : sources/RSS_feeds.txt)")
    parser.add_argument("-tw", dest="tw", type=Path, default=CHAINES_TWITCH, metavar="FICHIER",
                        help="fichier des chaînes Twitch (défaut : sources/Twitch_feeds.txt)")
    parser.add_argument("--local", type=Path, default=REGLAGES_FLUX,
                        help="réglages locaux (défaut : sources/flux_corrige_main.txt)")
    parser.add_argument("--no-twitch", action="store_true", help="ne pas inclure les chaînes Twitch")
    parser.add_argument("--no-previews", action="store_true", help="ne pas visiter les pages pour les aperçus")
    parser.add_argument("--no-cache", action="store_true", help="ignorer les caches (aperçus et Twitch)")
    parser.add_argument("--simple", action="store_true",
                        help="reconstruit seulement les pages à partir de la base et des caches : "
                             "aucun appel réseau, flux RSS non réécrits")
    return parser.parse_args(argv)


def limiter_par_source(items: list[dict], maximum: int) -> list[dict]:
    """Garde les `maximum` articles les plus récents de chaque source (0 = tous)."""
    if maximum <= 0:
        return items
    epoque = datetime.min.replace(tzinfo=timezone.utc)
    gardes, compte = [], {}
    for item in sorted(items, key=lambda i: i["date"] or epoque, reverse=True):
        compte[item["key"]] = compte.get(item["key"], 0) + 1
        if compte[item["key"]] <= maximum:
            gardes.append(item)
    return gardes


def copier_si_change(source: Path, cible: Path) -> bool:
    """Copie atomique (fichier temporaire puis renommage). False si la cible est déjà identique."""
    if cible.exists() and filecmp.cmp(source, cible, shallow=False):
        return False
    cible.parent.mkdir(parents=True, exist_ok=True)
    tmp = cible.with_name(cible.name + ".tmp")
    shutil.copyfile(source, tmp)
    tmp.replace(cible)
    return True


def ecrire_si_change(cible: Path, texte: str) -> None:
    if not cible.exists() or cible.read_text(encoding="utf-8") != texte:
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(texte, encoding="utf-8")


def copier_statiques() -> None:
    """Recopie static/ dans build/ : build/ contient ainsi tout le site, et rien d'autre n'est publié."""
    for source in sorted(STATIC.rglob("*")):
        if source.is_file():
            copier_si_change(source, BUILD / source.relative_to(STATIC))
    ecrire_si_change(BUILD / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {URL_SITE}/sitemap.xml\n")
    ecrire_si_change(BUILD / "sitemap.xml",
                     '<?xml version="1.0" encoding="UTF-8"?>\n'
                     '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                     f"<url><loc>{URL_SITE}/</loc><changefreq>daily</changefreq></url>\n"
                     f"<url><loc>{URL_SITE}/{NOM_VEILLE}</loc><changefreq>hourly</changefreq></url>\n"
                     "</urlset>\n")


def ecrire_atomique(sortie: Path, texte: str) -> None:
    """Écrit un fichier temporaire puis le renomme : la page n'est jamais à moitié écrite."""
    sortie.parent.mkdir(parents=True, exist_ok=True)
    tmp = sortie.with_name(sortie.name + ".tmp")
    tmp.write_text(texte, encoding="utf-8")
    tmp.replace(sortie)


def ecrire_accueil() -> None:
    """Recopie la page principale (accueil/index.html) dans build/index.html, sans rien y changer.
    Le bloc immuable est contrôlé avant et après l'écriture."""
    page = immuable.lire_source()
    immuable.verifier_page(page)
    sortie = BUILD / NOM_ACCUEIL
    if not sortie.exists() or sortie.read_text(encoding="utf-8") != page:
        ecrire_atomique(sortie, page)
    immuable.verifier_page(sortie.read_text(encoding="utf-8"))
    print(f"OK : page principale copiée dans {sortie.relative_to(ROOT)} (bloc immuable intact)")


def ecrire_veille(items: list[dict], previews: dict[str, dict], categories: dict[str, str]) -> None:
    """Écrit build/veille.html (le KiosKe)."""
    sortie = BUILD / NOM_VEILLE
    ecrire_atomique(sortie, render_page(items, previews, categories))
    print(f"OK : {len(items)} article(s) écrits dans {sortie.relative_to(ROOT)}")


def ecrire_flux_rss(items: list[dict], categories: dict[str, str]) -> None:
    flux = BUILD / "rss.xml"
    flux.write_text(render_rss(items), encoding="utf-8")
    print(f"OK : flux RSS écrit dans {flux.relative_to(ROOT)} ({min(len(items), RSS_MAX)} article(s))")

    # Un flux RSS par catégorie, dans rss/ : mêmes articles, filtrés sur la catégorie de leur source.
    dossier_rss = BUILD / DOSSIER_RSS_CATEGORIES
    dossier_rss.mkdir(parents=True, exist_ok=True)
    ordre = ordre_des_categories(items, categories)
    slugs = slugs_categories(ordre)
    for c in ordre:
        sous_ensemble = [i for i in items if categories.get(i["key"], AUTRES) == c]
        cible = dossier_rss / f"{slugs[c]}.xml"
        cible.write_text(render_rss(
            sous_ensemble,
            titre=f"Le {NOM_KIOSKE} : {c}",
            adresse_flux=f"{URL_SITE}/{DOSSIER_RSS_CATEGORIES}/{slugs[c]}.xml",
            description=f"Catégorie « {c} » du {NOM_KIOSKE} : articles et vidéos des sources suivies, mis à jour automatiquement.",
        ), encoding="utf-8")
        print(f"OK : flux de catégorie écrit dans {cible.relative_to(ROOT)} ({min(len(sous_ensemble), RSS_MAX)} article(s))")
    # Supprime les flux d'une catégorie qui n'existe plus.
    attendus = {f"{s}.xml" for s in slugs.values()}
    for ancien in dossier_rss.glob("*.xml"):
        if ancien.name not in attendus:
            ancien.unlink()
            print(f"supprimé (catégorie disparue) : {ancien.relative_to(ROOT)}")


def construire(args: argparse.Namespace) -> None:
    """Construit build/. Un seul build à la fois (verrou partagé avec la publication)."""
    with verrou():
        ignored, names = read_local(args.local)
        urls = [u for u in read_feeds(args.rss) if u not in ignored]
        chaines = read_twitch(args.tw)
        print(f"{len(urls)} flux RSS dans {args.rss.name} ({len(ignored)} ignoré(s) localement)")
        sources_actives = set(urls) | {f"twitch:{n}" for n in chaines}

        historique = Historique(HISTORIQUE_DB)
        if not args.simple:
            items = []
            with cf.ThreadPoolExecutor(max_workers=6) as pool:
                for feed_items in pool.map(lambda u: load_feed(u, names), urls):
                    items.extend(feed_items)
            if not args.no_twitch:
                print(f"{len(chaines)} chaîne(s) Twitch")
                items.extend(load_twitch(chaines, TWITCH_SCAN, use_cache=not args.no_cache))
            historique.enregistrer(items)
        # On affiche les articles des sources encore listées (les autres restent en base).
        items = limiter_par_source(historique.charger(sources_actives), ARTICLES_PAR_SOURCE)
        historique.fermer()
        print(f"historique : {len(items)} article(s) affiché(s) pour {len(sources_actives)} source(s) active(s)")

        links = [i["link"] for i in items if i.get("kind") != "twitch"]
        if args.simple:
            print("--simple : aucun appel réseau, flux RSS non réécrits")
            previews = apercus.apercus_des_liens(apercus.lire_cache(), links)
        elif args.no_previews:
            previews = {}
        else:
            previews = apercus.load_previews(links, use_cache=not args.no_cache)

        # Images des articles : téléchargées ici, servies par le site (le KiosKe ne charge rien d'un autre site).
        correspondance = telecharger_images(
            [i.get("image") for i in items] + [p.get("image") for p in previews.values()],
            telecharger=not args.simple)
        appliquer_images(items, previews, correspondance)
        # Purge : seulement avec les fichiers de sources habituels et tous les aperçus, sinon on effacerait à tort.
        if args.rss == FLUX_RSS and args.tw == CHAINES_TWITCH and not args.no_previews:
            supprimees = purger_images(set(correspondance.values()))
            if supprimees:
                print(f"[images] {supprimees} image(s) inutilisée(s) supprimée(s)")

        categories = read_categories(args.rss, args.tw)
        print(f"{len(set(categories.values()))} catégorie(s) lue(s) dans les fichiers de sources")
        ecrire_accueil()  # d'abord : si le bloc immuable a changé, rien n'est écrit
        ecrire_veille(items, previews, categories)
        if not args.simple:
            ecrire_flux_rss(items, categories)
        copier_statiques()


def main(argv: list[str] | None = None) -> None:
    construire(analyser_arguments(argv))
