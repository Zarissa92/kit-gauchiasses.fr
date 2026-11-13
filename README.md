# gauchiasses.fr

Site « Mélenchon 2027 » : deux pages statiques (HTML5 et CSS, **sans JavaScript**), sans publicité ni pistage.

- **La page principale** (`index.html`) : écrite à la main, avec son **bloc immuable** (cagnotte, 3 cartes,
  lien vers le KiosKe, lien Discord, code de conduite) et les collections de cartes Wikipédia des membres.
- **Le KiosKe** (`veille.html`) : une veille automatique des médias indépendants, des luttes et des voix
  LGBTQIA+, reconstruite toutes les 30 minutes sur le serveur à partir de flux RSS et de chaînes Twitch.

> Projet réorganisé le 2026-11-11 sur le modèle de `kioske.fr` : code dans le paquet `gauchiasses/`, site
> généré dans `build/`, réglages dans `gauchiasses.cfg`, déploiement par `deploy/gauchiasses.sh`.
> Le projet d'avant est dans `old/avant-reorganisation-2026-11-11.tar.gz`.

<p align="center"><img src="docs/img/accueil-zoom.png" width="420" alt="Panneau de la page principale : cagnotte, 3 cartes, lien vers le KiosKe, Discord"></p>

Sur le KiosKe, cliquer sur une étiquette ouvre la fenêtre de la source, avec une carte par article. Cliquer
sur une carte ouvre l'article dans la page (texte du flux, lien vers l'original).

<p align="center"><img src="docs/img/veille-entete.png" width="520" alt="En-tête du KiosKe et étiquettes des sources"></p>

Les captures `docs/img/veille-*.png` datent d'avant la réorganisation : elles sont à refaire.

## Sommaire

1. [Structure](#structure)
2. [Réglages : `gauchiasses.cfg`](#réglages--gauchiassescfg)
3. [Construire et publier](#construire-et-publier)
4. [Bloc immuable](#bloc-immuable)
5. [La page principale et ses cartes](#la-page-principale-et-ses-cartes)
6. [Le KiosKe](#le-kioske)
7. [Données, caches et images](#données-caches-et-images)
8. [Déploiement sur le serveur](#déploiement-sur-le-serveur)
9. [Référencement](#référencement)
10. [Limites](#limites)
11. [Licences](#licences)

## Structure

| Fichier / dossier | Rôle |
| --- | --- |
| `gauchiasses.cfg` | **Tous les réglages** : domaine, veille, cartes, serveur, thèmes. Lu par Python et par les scripts bash. |
| `accueil/index.html` | Source de la page principale. Écrite à la main, sauf deux zones remplies par le build des cartes. Contient le bloc immuable. |
| `listes/` | Fichiers texte des cartes de la page principale, un par collection. Écrits à la main. |
| `sources/` | Ce que le KiosKe suit : `RSS_feeds.txt`, `Twitch_feeds.txt`, `flux_corrige_main.txt`. Écrits à la main. |
| `static/` | Fichiers publiés tels quels : `favicon.svg`, `apple-touch-icon.png`, `preview.png`, `fonts/`, et `img/cartes/` si une liste fournit une image locale. |
| `gauchiasses/` | Le code (paquet Python) et les feuilles de style du KiosKe `style.css`, `pluie.css`. Voir ci-dessous. |
| `bin/` | Points d'entrée : `build_site.py`, `publier_public.py`, `garde_immuable.py`, `construire_cartes.py`. Quelques lignes chacun. |
| `deploy/` | Scripts du serveur : `gauchiasses.sh` (point d'entrée), `installer_serveur.sh`, `deployer_nginx.sh`, `verifier_serveur.sh`, `lib_config.sh`, `systemd/`, `fail2ban/`. |
| `data/` | `immuable.json` (empreinte du bloc, suivie par git) ; `historique.db`, `cache/`, `build.lock` (locaux, jamais publiés). |
| `build/` | **Le site généré**, complet : `index.html`, `veille.html`, `rss.xml`, `rss/`, `img/veille/`, copie de `static/`, `robots.txt`, `sitemap.xml`. Hors git, jamais édité à la main, jamais envoyé au serveur. |
| `requirements.txt` | Dépendances Python (`feedparser`, `yt-dlp`, `legacy-cgi`). |
| `apercu/preview.svg` | Source de `static/preview.png` : `rsvg-convert -w 1200 -h 630 apercu/preview.svg -o static/preview.png`. |
| `docs/img/` | Captures de ce README. |
| `old/` | Sauvegardes et reliquats (hors git, non synchronisés). `old/reliquats-2026-11-11/` : anciens scripts (`bin/`, `deploy/`), ancien dossier `export/`, `redirections/`, `bin/sauvegarde_logs.sh`. |

Le paquet `gauchiasses/` :

| Module | Rôle |
| --- | --- |
| `config.py` | Chemins du projet et valeurs de `gauchiasses.cfg`. Aucun autre module n'écrit de chemin en dur. |
| `sources.py` | Lecture des fichiers de `sources/` (flux, chaînes, réglages locaux, catégories). |
| `flux.py`, `twitch.py`, `apercus.py`, `reseau.py` | Récupération : flux RSS, vidéos Twitch (yt-dlp), aperçus Open Graph. |
| `images.py` | Téléchargement des images des articles dans `build/img/veille/`, et purge de celles qui ne servent plus. |
| `historique.py` | Base SQLite de tout ce qui a été récupéré. |
| `themes.py`, `style.css`, `pluie.css` | Thèmes et CSS du KiosKe. |
| `rendu.py`, `rss.py`, `texte.py` | HTML du KiosKe, flux RSS produits, outils de texte. |
| `cartes.py` | Build des cartes Wikipédia de la page principale (sur le PC seulement). Son CSS est dans `style_html`. |
| `immuable.py` | Garde du bloc immuable. |
| `verrou.py` | Un seul build ou une seule publication à la fois. |
| `construction.py`, `publication.py` | Le build (`build/`) et la copie vers la racine web. |

## Réglages : `gauchiasses.cfg`

Format INI, commenté dans le fichier. Une valeur manquante ou invalide arrête le build avec un message.

| Section | Clés |
| --- | --- |
| `[site]` | `domaine`, `nom` (nom du site annoncé par le KiosKe quand on partage son lien). |
| `[veille]` | `nom` (KiosKe), `slogan`, `theme` (thème par défaut), `articles_flux_rss` (100), `videos_par_chaine` (15), `articles_par_source` (0 = tous), `delai_nouvel_essai_heures` (24). |
| `[cartes]` | `periode_etiquettes` (secondes), `police` (demande `static/fonts/<nom>.woff2`). |
| `[serveur]` | `racine_web` (`/var/www/gauchiasses.fr`), `ip_publique`, `intervalle_timer` (`30min`). |
| `[theme.<nom>]` | `nom`, `fond` (`etoiles` ou `noir`), `pluie` (`oui` ou `non`), `opacite_panneau` (0 à 100, en %). |

Deux thèmes existent pour le KiosKe : `pluie` (pluie matricielle, panneau opaque, thème par défaut : celui de
la page principale) et `voie_lactee` (fond noir étoilé). Ajouter une section `[theme.<nom>]` ajoute un bouton
de choix sur le KiosKe ; avec un seul thème, aucun bouton n'est affiché.

Les titres et textes de la page principale ne sont pas dans ce fichier : ils s'écrivent dans
`accueil/index.html`.

Les scripts bash lisent les mêmes valeurs avec `cfg <section> <clé>` (`deploy/lib_config.sh`).
Après un changement de `intervalle_timer` ou de `racine_web`, relancer `deploy/installer_serveur.sh`.

## Construire et publier

Le Python est toujours celui du venv du projet : `venv_blog/` sur le PC, `venv/` sur le serveur.

```bash
python3 -m venv venv_blog && venv_blog/bin/pip install -r requirements.txt   # une fois

venv_blog/bin/python bin/build_site.py                 # build complet : flux, Twitch, aperçus, images, pages, flux RSS
venv_blog/bin/python bin/build_site.py --simple        # pages seules, sans réseau (base et caches), flux RSS non réécrits
venv_blog/bin/python bin/build_site.py --no-twitch     # sans Twitch
venv_blog/bin/python bin/build_site.py --no-previews   # sans visiter les pages (rapide)
venv_blog/bin/python bin/build_site.py --no-cache      # ignore les caches
```

Le résultat est dans `build/` : ouvrir `build/index.html` ou `build/veille.html` dans un navigateur suffit
pour le voir. Chaque build recopie `accueil/index.html` dans `build/index.html` sans rien y changer.

La publication copie `build/` dans la racine web (`racine_web`). Elle se lance **sur le serveur** :

```bash
venv/bin/python bin/publier_public.py                # construit, puis copie (ce que fait le timer)
venv/bin/python bin/publier_public.py --simple       # construit sans réseau, puis copie
venv/bin/python bin/publier_public.py --sans-build   # copie build/ tel quel
```

- Seuls les fichiers dont le contenu a changé sont copiés ; la dernière ligne donne le compte.
- Les images et flux de catégorie qui ne sont plus dans `build/` sont retirés de la racine web.
- S'il manque une page, le flux `rss.xml`, la police ou une icône dans `build/`, rien n'est publié.
- Le build, le build des cartes et la publication partagent un verrou (`data/build.lock`) : un lancement
  manuel pendant le passage du timer attend la fin de l'autre au lieu d'écrire les mêmes fichiers.

**Changer la page principale, le thème ou la mise en page sans toucher aux articles** : `gauchiasses_update`
depuis le PC, puis sur le serveur `venv/bin/python bin/publier_public.py --simple`. Un build seul ne publie rien.

## Bloc immuable

Dans `accueil/index.html`, la zone entre `<!-- IMMUABLE:DEBUT -->` et `<!-- IMMUABLE:FIN -->` contient la
cagnotte, les 3 cartes côte à côte, le lien vers le KiosKe, le lien Discord et le code de conduite.
**Aucun build ne la modifie.** Deux contrôles (`gauchiasses/immuable.py`) :

1. le bloc de la source doit correspondre à l'empreinte de `data/immuable.json` ;
2. la page de `build/` doit contenir ce bloc **à l'identique**, avant et après son écriture, et encore
   avant la publication.

```bash
venv_blog/bin/python bin/garde_immuable.py verifier      # échoue si le bloc a changé
venv_blog/bin/python bin/garde_immuable.py enregistrer   # accepte la version actuelle (après une modif voulue)
```

Tant que l'empreinte n'est pas réenregistrée après une modification, rien n'est écrit ni publié.
Le déplacement de la page (de `index.html` vers `accueil/index.html`, le 2026-11-11) n'a pas changé
l'empreinte : elle porte sur le contenu du bloc, pas sur le fichier.

## La page principale et ses cartes

`accueil/index.html` s'écrit à la main, sauf deux zones remplies par le build des cartes :

- `NUAGE-TAGS` (style et nuage des collections), juste avant le bloc immuable ;
- `CARTES-TEXTE` (fenêtres des collections et cartes), après le bloc immuable.

Le reste est à toi : l'en-tête (titre, description, mots-clefs, données `schema.org`), le bouton
« Qui sommes-nous » (entre `QUI-SOMMES-NOUS:DEBUT` et `QUI-SOMMES-NOUS:FIN`), l'icône « Flux RSS du KiosKe »,
le message « Découvre les collections des membres », les fiches des 3 cartes (`FICHES`).

### Build des cartes

Il tourne **sur le PC**, jamais sur le serveur : il interroge Wikipédia et garde ses caches dans
`data/cache/`. Le serveur reçoit `accueil/index.html` déjà construit.

```bash
venv_blog/bin/python bin/construire_cartes.py                     # toutes les listes de listes/*.txt
venv_blog/bin/python bin/construire_cartes.py listes/Vipex.txt    # seulement ces fichiers
venv_blog/bin/python bin/construire_cartes.py --hors-ligne        # sans interroger Wikipédia (caches seulement)
venv_blog/bin/python bin/construire_cartes.py --periode=8         # période du passage au rouge des étiquettes
venv_blog/bin/python bin/construire_cartes.py --police="Russo One"
```

Sans `--periode` ni `--police`, les valeurs viennent de `[cartes]` dans `gauchiasses.cfg`. Le script écrit
les deux zones, vérifie le bloc immuable avant et après, puis recopie la page dans `build/index.html`.
Le rapport des cartes exclues est dans `data/cache/rapport_cartes.txt`.

Premier build, ou après un changement de `VERSION_CACHE` ou `VERSION_FICHIERS` (`gauchiasses/cartes.py`) :
environ 3 minutes (une requête par lot, avec une pause d'une seconde). Si Wikipédia limite le débit
(HTTP 429), le script attend et réessaie tout seul. Les caches sont sauvegardés à chaque lot.

### Format des listes

Deux formats, mélangeables dans un même fichier. Les lignes qui commencent par `#` sont ignorées.

**1. Format copié-collé** : le titre, suivi de `N cartes` (le nombre n'est pas utilisé), puis pour chaque
carte le nom, la description, et une rareté facultative, ignorée (`RARETES` dans `gauchiasses/cartes.py`).
Un emoji en fin de titre passe en tête à l'affichage (« Vipex🚩 » donne « 🚩Vipex »).

```text
Vipex🚩
19 cartes
Marc Bloch
historien et résistant français
Mythique
```

**2. Format wikipick** : un titre seul sur sa ligne (un chiffre, le titre, le nombre entre parenthèses),
puis des cartes en gras, séparées par une ligne vide. La ligne `image:` est facultative.

```text
5🚩Vipex (19)

**Marine Le Pen**
femme politique française
image: https://fr.wikipedia.org/wiki/Fichier:Exemple.jpg
```

| Forme de `image:` | Effet |
| --- | --- |
| `image: photos/nom.jpg` | Fichier local, relatif au fichier texte. Copié dans `static/img/cartes/`. |
| `image: Fichier:Nom.gif` ou `image: File:Nom.jpg` | Fichier Wikimédia : URL, auteur et licence récupérés. |
| `image: https://fr.wikipedia.org/wiki/Fichier:…` (ou `commons.wikimedia.org/wiki/File:…`) | Idem, à partir du lien de la page du fichier. |
| `image: https://…` | URL d'image directe, sans crédit automatique. |
| (absent) | Image principale de l'article Wikipédia, sinon celle de son infobox (`image =`, puis `logo =`), sinon l'initiale. |

Le nom d'une carte doit correspondre à une page de fr.wikipedia.org. Les pages absentes et les pages
d'homonymie sont exclues ; une même page n'apparaît qu'une fois. Une ligne qui ne correspond à aucun format
arrête le build avec son numéro.

| Message | Solution |
| --- | --- |
| `format non reconnu` | Ajouter le `**` au nom, ou vérifier la ligne vide avant le bloc. |
| `image introuvable : …` | Corriger le chemin, relatif au fichier texte. |
| `URL refusée (http, pas https)` | Utiliser `https://`. |
| `absent(s) du cache, refusés (--hors-ligne)` | Relancer sans `--hors-ligne`, avec une connexion. |
| `Le bloc immuable a été modifié` | Restaurer le bloc, ou réenregistrer l'empreinte si la modification est voulue. |
| `section « cartes » introuvable` | Vérifier que `accueil/index.html` est bien la page principale. |
| `police … : fichier absent` | Mettre le fichier `.woff2` dans `static/fonts/`. |

### Avant d'envoyer

1. Modifier les listes dans `listes/`, puis lancer `bin/construire_cartes.py`.
2. Lire `data/cache/rapport_cartes.txt` : pages absentes, homonymies, doublons.
3. Ouvrir `build/index.html` : nuage, fenêtres, boutons « + », 3 cartes, bouton « Qui sommes-nous ».
4. `gauchiasses_update --dry-run`, puis `gauchiasses_update` (voir [Déploiement](#déploiement-sur-le-serveur)).

### Apparence

- Pluie de fond (CSS pur, écrite dans `accueil/index.html`) : violet en tête (`--r-tete`), rouge (`--r-haut`),
  rose foncé (`--r-moyen`), bleu-violet en queue (`--r-bas`).
- Panneaux et cartes opaques ; pas de halo sur les textes courants ; seuls les titres principaux et les
  étiquettes gardent leur effet, et les étiquettes passent au rouge à tour de rôle.
- Image d'une carte : réduite pour tenir entièrement (`object-fit: contain`), sans recadrage.
- Les variables CSS de la zone `NUAGE-TAGS` sont réécrites à chaque build : pour les garder, les changer
  dans `style_html` (`gauchiasses/cartes.py`).
- Icônes : `static/favicon.svg` et `static/apple-touch-icon.png`
  (`rsvg-convert -w 180 -h 180 static/favicon.svg -o static/apple-touch-icon.png`).

## Le KiosKe

### Sources

Dans `sources/`. Une ligne `[Nom]` seule ouvre une catégorie ; les flux ou chaînes qui suivent y vont,
jusqu'à la ligne `[…]` suivante. Une source sans catégorie tombe dans le bloc « Des Liens », en dernier.

```text
[Médias d'enquête]
"https://portail.basta.media/spip.php?page=backend"
[Twitch]
"ostpolitik"
```

- `RSS_feeds.txt` et `Twitch_feeds.txt` sont des **copies** des listes du bot Discord (`RSS_feeds.txt` et
  `Twich_feeds.txt` dans `discord-rss-bot`) : si l'une des deux versions change, recopier l'autre.
- `flux_corrige_main.txt` : réglages locaux. `!"URL"` ignore un flux, `"URL" | Nom` change son nom
  affiché (flux RSS seulement). Pas de commentaire en fin de ligne. Un flux qui ne fournit pas de
  titre donne une étiquette vide (seulement « ×10 ») : lui donner un nom ici, comme pour
  `agauche.org` (« À gauche »). Le nom apparaît au build complet suivant, pas avec `--simple`.
- Une source présente dans deux catégories garde la première. Les étiquettes sont regroupées par URL :
  un flux renommé n'apparaît qu'une fois.

### La page

- **Retour** : le bouton « ← Retour au site » pointe vers la page principale.
- **Thème au choix du visiteur** : boutons radio cachés et règles `:root:has(#theme-<id>:checked)`, CSS
  seul, sans JavaScript ni cookie. Le choix ne dure que la visite. Sans `:has()` (vieux navigateurs), seul
  le thème par défaut s'affiche.
- **Étiquettes** : une par source, dans un bloc par catégorie, avec l'icône du flux RSS de la catégorie.
- **Fenêtres et articles** : `popover` HTML, sans JavaScript. La carte est un bouton ; le panneau de
  l'article affiche image, date, source, texte complet du flux et lien vers le site d'origine.
- **Images** : téléchargées par le build et servies par le site. Le KiosKe ne charge rien d'un autre site.
- **Téléphone** (640 px et moins) : une carte par ligne, image en haut, seul le titre est affiché ; les
  étiquettes passent à la ligne ; les fenêtres ont la largeur du panneau principal.
- **Grand écran** (1100 px et plus) : `zoom: 1.25`, fenêtres de catégorie sur trois colonnes, blocs de
  catégories sur deux colonnes dès 900 px. Largeur et hauteur des fenêtres sont divisées par 1,25 pour
  tenir dans l'écran.
- **Lisibilité** : cartes, fenêtres et panneaux d'article opaques ; l'opacité du grand panneau principal
  vient de `opacite_panneau`. Pas de halo sur les textes courants ; halo réduit sur le titre. Les
  étiquettes ne clignotent pas.

Le CSS est dans `gauchiasses/style.css` (et `gauchiasses/pluie.css`), inséré dans la page au build.

### Flux RSS produits

`build/rss.xml` (les 100 articles les plus récents) et un flux par catégorie dans `build/rss/`
(`rss/medias-d-enquete.xml` pour « Médias d'enquête », `rss/des-liens.xml` pour les sources sans catégorie),
avec le **texte complet** de chaque article, pour qu'il se lise dans Akregator ou Thunderbird sans ouvrir le
site. Dates à l'heure de Paris, au format RFC 822. Un flux dont la catégorie a disparu est supprimé. Le
KiosKe déclare chaque flux dans son en-tête.

## Données, caches et images

- **`data/historique.db`** (SQLite, table `articles`) : tout ce qui a été récupéré. Rien n'y est effacé
  automatiquement. Le KiosKe affiche les articles des sources **encore listées** : retirer une ligne de
  `sources/` cache ses articles sans les supprimer. `articles_par_source` limite l'affichage sans
  toucher à la base. Un flux injoignable ne fait rien disparaître.
- **`data/cache/`** : `previews_cache.json` (aperçus), `twitch_cache.json`, `images_echecs.json`, et pour les
  cartes `cache_wikipedia.json`, `cache_images.json`, `rapport_cartes.txt`. Une page ou une image en échec
  est réessayée après `delai_nouvel_essai_heures`.
- **Images du KiosKe** : téléchargées dans `build/img/veille/` sous un nom dérivé de leur adresse. JPEG,
  PNG, WebP, GIF et AVIF seulement (pas de SVG), 5 Mo au maximum. Les images qu'aucun article affiché
  n'utilise plus sont supprimées à chaque build.
- **Images de la page principale** : celles des cartes et du bloc immuable sont chargées depuis Wikimédia.
  C'est la seule ressource que le site charge ailleurs (voir [Limites](#limites)).

## Déploiement sur le serveur

Le site est construit et servi par le serveur (Debian 13, nginx). Le projet vit dans
`/home/meli/gauchiasses.fr`, la racine servie est `racine_web` (`/var/www/gauchiasses.fr`).

**Depuis le PC** : la fonction fish `gauchiasses_update` (rsync avec `--delete`).

```bash
gauchiasses_update --dry-run    # ce qui serait envoyé
gauchiasses_update              # envoi vers meli@zarisse.fr:/home/meli/gauchiasses.fr/
```

Elle ne doit envoyer ni `build/`, ni `data/historique.db`, ni `data/cache/`, ni `data/build.lock`, ni les
venvs, ni `old/`, `export/`, `docs/`, `apercu/`, `.git/`, `.claude/`, `CLAUDE.md`. `static/` (dont
`preview.png`), `accueil/` et `data/immuable.json` doivent toujours partir : sans eux, rien n'est publié.
La fonction à jour est donnée plus bas, dans « Après la réorganisation ».

**Sur le serveur**, en utilisateur normal (`meli`) ; les étapes qui en ont besoin demandent `sudo` :

```bash
bash deploy/gauchiasses.sh                          # tout, dans l'ordre
bash deploy/gauchiasses.sh --email toi@exemple.fr   # tout, et demande le certificat Let's Encrypt
bash deploy/gauchiasses.sh veille                   # seulement la mise à jour (ce que lance le timer)
bash deploy/gauchiasses.sh --simulation             # affiche sans rien lancer
```

| Étape | Ce qu'elle fait |
| --- | --- |
| `immuable` | Vérifie l'empreinte du bloc immuable. |
| `serveur` | `installer_serveur.sh` : venv, racine web, unités systemd, premier passage. |
| `veille` | `publier_public.py` : construit `build/` puis le copie dans la racine web. |
| `nginx` | `deployer_nginx.sh` : HTTP, puis HTTPS si le certificat existe. Options `--email`, `--sans-certificat`. |
| `fail2ban` | Page « Tu es banni » et jail `gauchiasses-scan`. Ignorée si la jail `sans_pitie` manque. |
| `statut` | `verifier_serveur.sh` : DNS, nginx, les deux pages en HTTPS, certificat, timer, âge de la dernière publication. |

**Service** : le timer `gauchiasses-veille` lance `deploy/gauchiasses.sh veille` à l'intervalle de
`gauchiasses.cfg`. Les modèles sont dans `deploy/systemd/` ; `installer_serveur.sh` y remplace l'utilisateur,
le dossier, la racine web et l'intervalle. Le service tourne sous `meli` (`Group` = son groupe principal,
calculé par `id -gn "$UTILISATEUR"`), avec `SupplementaryGroups=www-data`, `UMask=0002` et
`ExecStartPost=+chown -R www-data:www-data` sur la racine web.

```bash
systemctl list-timers gauchiasses-veille.timer
journalctl -u gauchiasses-veille.service -n 50
sudo systemctl start gauchiasses-veille.service   # publier tout de suite
```

**Droits** : la racine web est en `www-data:www-data`, dossiers `2775`, fichiers `664`. `data/` et
`build/` appartiennent à l'utilisateur du service. Il n'y a plus besoin de rendre `/home/meli` traversable.

**nginx** (`deploy/deployer_nginx.sh`) : le fichier `/etc/nginx/sites-available/gauchiasses.fr` est
**généré** par ce script, il ne s'édite pas à la main. HTTPS seul avec HSTS, **TLS 1.3 seul**, 0-RTT refusé,
version masquée, méthodes `GET` et `HEAD`, fichiers cachés refusés, en-têtes de sécurité. Politique de
contenu : `default-src 'none'`, aucun script, styles et polices du site seulement, images du site ou d'un
autre site en HTTPS (`img-src 'self' data: https:`, pour les images Wikimédia de la page principale). Le
script teste la configuration et remet l'ancienne si elle est invalide. Le certificat couvre le domaine
seul, sans `www`. `--desinstaller` retire le site (certificats conservés).

**fail2ban** (`deploy/fail2ban/`) : `f2b.sh` (copie de `~/fail2ban_hardened/f2b.sh`), filtre
`gauchiasses-scan.conf` (fichiers cachés, PHP, WordPress, `/cgi-bin/`), jail `gauchiasses-scan.jail.conf`
(5 scans en 10 minutes, ban d'un jour, appliqué par nginx : page « Tu es banni »). Débannir :
`sudo fail2ban-client set gauchiasses-scan unbanip <IP>`.

**Domaines alternatifs** : `gauchiasse.org` et `gauchiasses.org` redirigent vers `gauchiasses.fr` (301), en
gardant le chemin. Le script est dans `~/Lenovo_scripts/redirections_gauchiasses.sh`, à lancer en root sur le
serveur. Vérifier : `curl -I https://gauchiasse.org`.

### Après la réorganisation du 2026-11-11

Tant que ces étapes ne sont pas faites, le serveur continue de servir l'ancien dossier `public/`.

1. Remplacer la fonction fish `gauchiasses_update` (`~/.config/fish/functions/gauchiasses_update.fish`) :

   ```fish
   function gauchiasses_update --description "Envoie gauchiasses.fr vers meli@zarisse.fr:/home/meli/gauchiasses.fr/ (rsync --delete). Arguments en plus passés à rsync, ex: gauchiasses_update --dry-run"
       set -l src /home/melissandre/gauchiasses.fr/
       set -l dest meli@zarisse.fr:/home/meli/gauchiasses.fr/

       if not test -d $src
           echo "Source introuvable : $src" >&2
           return 1
       end

       # Exclus : dossiers locaux ; site généré sur le serveur (build/) ; données du serveur
       # (data/historique.db, data/cache/, data/build.lock : jamais écrasées par le PC) ;
       # venvs, sauvegardes et fichiers temporaires.
       # /public/ : ancienne racine web, gardée le temps que nginx serve /var/www/gauchiasses.fr
       # (exclusion à retirer ensuite).
       # static/ (dont preview.png), accueil/ et data/immuable.json sont envoyés : la publication en a besoin.
       rsync -avz --checksum --delete --human-readable --progress \
           --exclude='.git/' --exclude='.claude/' --exclude='apercu/' --exclude='docs/' \
           --exclude='venv/' --exclude='venv_blog/' --exclude='/build/' --exclude='/public/' \
           --exclude='old/' --exclude='export/' --exclude='data/cache/' \
           --exclude='data/historique.db' --exclude='data/build.lock' --exclude='CLAUDE.md' \
           --exclude='.directory' --exclude='*.swp' --exclude='.DS_Store' \
           --exclude='__pycache__/' --exclude='*.tmp' \
           $argv $src $dest
   end
   ```

2. `gauchiasses_update --dry-run`, puis `gauchiasses_update`. L'envoi retire du serveur les anciens fichiers
   de la racine du projet (`index.html`, `veille.html`, `rss/`, anciens scripts) ; `public/` reste en place.
3. Sur le serveur : `bash deploy/installer_serveur.sh`. Il crée `/var/www/gauchiasses.fr`, réinstalle les
   unités systemd (le timer lance désormais `deploy/gauchiasses.sh veille`) et fait un premier passage, qui
   télécharge les images du KiosKe (quelques minutes).
4. `bash deploy/deployer_nginx.sh` : nginx sert la nouvelle racine. Puis `bash deploy/gauchiasses.sh fail2ban`.
5. Vérifier : `bash deploy/verifier_serveur.sh`.
6. Ensuite seulement : supprimer `/home/meli/gauchiasses.fr/public/` sur le serveur, et retirer l'exclusion
   `/public/` de `gauchiasses_update`.

## Référencement

- **Page principale** : titre, descriptions, mots-clefs (gauchiasses, gauche, Mélenchon, 2027, votez, La
  France insoumise), balises Open Graph et Twitter, données `schema.org` (JSON-LD) : tout est écrit à la main
  dans l'en-tête de `accueil/index.html`. Les 3 cartes du bloc immuable ont un texte alternatif.
- **KiosKe** : le titre et la description décrivent son contenu réel (`nom` et `slogan` de
  `gauchiasses.cfg`, nombre de sources et noms des catégories du jour). Adresse canonique, balises Open
  Graph et Twitter (image `preview.png`), flux RSS déclarés dans l'en-tête.
- Le build écrit `robots.txt` et `sitemap.xml` (les deux pages).

## Limites

- **Images de Wikimédia sur la page principale** : les cartes et les 3 cartes du bloc immuable chargent
  leurs images depuis `wikimedia.org`. Les héberger sur le site demanderait de modifier le bloc immuable.
- Un flux injoignable est ignoré avec un message `[flux] …` ; la page est construite sans lui.
- Twitch passe par yt-dlp. Une vidéo réservée aux abonnés ou supprimée est ignorée avec un message.
- Les aperçus viennent de la page de l'article ; certains sites ne fournissent pas d'image.
- La base n'est jamais purgée : sans `articles_par_source`, le KiosKe grossit avec le temps.
- Ne pas mettre dans la veille une ressource dont le nom se résout en adresse privée
  (ex. `blog.zarisse.fr` depuis le réseau local) : Chrome demande alors l'accès au réseau local.

## Licences

Textes des cartes : Wikipédia, CC BY-SA 4.0. Images des cartes : Wikimedia Commons ou Wikipédia, auteur.ice
et licence indiqué.e.s dans la fiche de chaque carte. Articles et vidéos du KiosKe : leurs auteur.ice.s et
sites respectifs. Police Russo One : SIL Open Font License (`static/fonts/OFL.txt`).
