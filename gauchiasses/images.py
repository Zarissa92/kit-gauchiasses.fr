"""Images des articles du KiosKe : téléchargées dans build/img/veille, jamais chargées depuis un autre site."""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .config import BUILD, CACHE_DIR, DELAI_ECHEC, DOSSIER_IMAGES
from .reseau import UA

ECHECS_IMAGES = CACHE_DIR / "images_echecs.json"  # URL en échec -> date ; réessayée après DELAI_ECHEC

IMAGE_MAX = 5 * 1024 * 1024  # au-delà, l'image est ignorée
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
               "image/gif": ".gif", "image/avif": ".avif"}  # SVG exclu : il peut contenir du script


def chemin_image(url: str) -> str:
    """Nom de base de l'image d'une URL : un hash stable de l'adresse (sans l'extension)."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def image_locale(url: str | None, telecharger: bool = True) -> str:
    """Chemin relatif à la racine (ex. img/veille/abc.jpg) de l'image d'une URL, déjà présente
    ou téléchargée maintenant. Chaîne vide si elle n'est pas disponible."""
    if not url:
        return ""
    for ext in IMAGE_TYPES.values():
        if (BUILD / DOSSIER_IMAGES / (chemin_image(url) + ext)).exists():
            return f"{DOSSIER_IMAGES}/{chemin_image(url)}{ext}"
    return telecharger_image(url) if telecharger else ""


def telecharger_image(url: str) -> str:
    """Télécharge une image (type et taille vérifiés). Chaîne vide en cas d'échec."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        ext = IMAGE_TYPES.get(resp.headers.get_content_type())
        if not ext:
            raise ValueError("type d'image non accepté")
        data = resp.read(IMAGE_MAX + 1)
    if len(data) > IMAGE_MAX:
        raise ValueError("image trop grosse")
    dest = BUILD / DOSSIER_IMAGES / (chemin_image(url) + ext)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    return f"{DOSSIER_IMAGES}/{dest.name}"


def telecharger_images(urls: list[str | None], telecharger: bool = True) -> dict[str, str]:
    """Associe chaque URL d'image à son chemin local (chaîne vide si indisponible).
    Sans `telecharger` : seulement les images déjà présentes, aucun appel réseau."""
    uniques = sorted({u for u in urls if u and u.startswith(("http://", "https://"))})
    echecs = json.loads(ECHECS_IMAGES.read_text(encoding="utf-8")) if ECHECS_IMAGES.exists() else {}
    maintenant = datetime.now(timezone.utc).timestamp()
    resultat = {u: image_locale(u, telecharger=False) for u in uniques}
    a_telecharger = [u for u in uniques if telecharger and not resultat[u]
                     and maintenant - echecs.get(u, 0) > DELAI_ECHEC]
    if a_telecharger:
        print(f"[images] {len(a_telecharger)} image(s) à télécharger", flush=True)
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(telecharger_image, u): u for u in a_telecharger}
        for f in cf.as_completed(futures):
            u = futures[f]
            try:
                resultat[u] = f.result()
                echecs.pop(u, None)
            except Exception as exc:  # une image en erreur ne bloque pas la page
                print(f"[image] {u} ignorée : {exc}", flush=True)
                echecs[u] = maintenant
    if telecharger:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        ECHECS_IMAGES.write_text(json.dumps(echecs, indent=1), encoding="utf-8")
    return resultat


def appliquer_images(items: list[dict], previews: dict[str, dict], correspondance: dict[str, str]) -> None:
    """Remplace les URL distantes par les chemins locaux (les caches gardent les URL d'origine)."""
    for item in items:
        item["image"] = correspondance.get(item.get("image") or "", "")
    for preview in previews.values():
        preview["image"] = correspondance.get(preview.get("image") or "", "")


def purger_images(utilisees: set[str]) -> int:
    """Supprime de build/img/veille les images qu'aucun article affiché n'utilise plus.
    `utilisees` : chemins relatifs (img/veille/abc.jpg). Renvoie le nombre de fichiers supprimés."""
    gardees = {Path(c).name for c in utilisees if c}
    supprimees = 0
    for fichier in (BUILD / DOSSIER_IMAGES).glob("*"):
        if fichier.is_file() and fichier.name not in gardees:
            fichier.unlink()
            supprimees += 1
    return supprimees
