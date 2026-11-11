# gauchiasses.fr

Page « Mélenchon 2027 » (HTML5/CSS, sans JavaScript) et sa page de veille automatique.
Le dossier contient la page principale, les scripts qui génèrent la veille, et le
build qui construit les cartes Wikipédia à partir de fichiers texte.

## Aperçus

**Page principale** : le panneau avec la cagnotte, les 3 cartes, le lien vers la veille, le Discord et le code de conduite.

<p align="center"><img src="docs/img/accueil-zoom.png" width="420" alt="Panneau de la page principale : cagnotte, 3 cartes, lien veille, Discord"></p>

**Page KiosKe (`veille.html`)** : un panneau avec le titre et des étiquettes, une par source, rangées par catégorie (un bloc titré par catégorie). Cliquer sur une étiquette ouvre la liste des articles de cette source.

<p align="center"><img src="docs/img/veille-entete.png" width="520" alt="En-tête de la veille et liste des sources repliées"></p>

La page de veille s'appelle **KiosKe** (« Le KiosKe ») depuis le 2026-11-10.

**Une section dépliée** (capture faite sur une copie de la page avec les sections ouvertes) : chaque carte affiche la miniature, la date, le titre et l'extrait.

<p align="center"><img src="docs/img/veille-cartes.png" width="520" alt="Cartes d'une source : miniature, date, titre et extrait"></p>

## Sommaire

1. [Structure](#structure)
2. [Éléments immuables](#éléments-immuables)
3. [Veille automatique](#veille-automatique)
4. [Build des cartes](#build-des-cartes)
5. [Déploiement sur le serveur](#déploiement-sur-le-serveur)
6. [Redirections (domaines alternatifs)](#redirections-domaines-alternatifs)
7. [SEO et mots-clefs](#seo-et-mots-clefs)
8. [Limites et sécurité](#limites-et-sécurité)
9. [Licences](#licences)

## Structure

| Fichier / dossier | Rôle |
| --- | --- |
| `index.html` | Page principale. Modifiée à la main. Le bloc immuable n'est jamais touché par un build. |
| `favicon.svg` | Favicon du site, utilisée par `index.html` et `veille.html`. |
| `bin/build_site.py` | Construit le KiosKe (page de veille) `veille.html`, le flux `rss.xml` et les flux par catégorie `rss/`, à la racine. |
| `RSS_feeds.txt` | Liste des flux RSS lue par `build_site.py` (copie de celle du bot Discord). |
| `Twich_feeds.txt` | Liste des chaînes Twitch lue par `build_site.py` (copie de celle du bot Discord). |
| `flux_corrige_main.txt` | Réglages locaux de la veille : ignorer un flux, changer son nom affiché. Le format est expliqué dans le fichier lui-même (commentaires en tête). |
| `veille.html` | Page KiosKe (veille) générée à la racine. Ne pas la modifier à la main. |
| `rss.xml` | Flux RSS du KiosKe entier (100 articles), généré par `build_site.py`. |
| `rss/` | Un flux RSS par catégorie (`rss/<nom>.xml`), généré par `build_site.py`. |
| `apple-touch-icon.png` | Icône de l'écran d'accueil (180×180), dérivée de `favicon.svg`. Copiée dans `public/` par `publier_public.py`. |
| `deploy/verifier_serveur.sh` | Contrôle de la mise en ligne sur le serveur (DNS, nginx, HTTPS, timers). |
| `data/historique.db` | Base SQLite de tous les articles déjà récupérés. Jamais publiée. |
| `bin/garde_immuable.py` | Vérifie que le bloc immuable de `index.html` n'a pas changé. |
| `data/immuable.json` | Empreinte de référence du bloc immuable. |
| `deploy/installer_serveur.sh`, `deploy/installer_serveur.fish` | Installation sur le serveur : venv, `public/`, timer systemd (toutes les 30 min). |
| `deploy/synchroniser.sh` | Copie le projet du PC vers le serveur (rsync, sans l'historique ni le venv). |
| `deploy/deployer_nginx.sh` | Configure nginx pour `gauchiasses.fr` sur le serveur, avec le certificat Let's Encrypt. |
| `deploy/nginx-gauchiasses.conf` | Ancienne référence nginx, remplacée par `deployer_nginx.sh`. |
| `bin/publier_public.py` | Construit la veille, vérifie le bloc immuable, copie le site dans `public/` : `index.html`, `favicon.svg`, `apple-touch-icon.png`, `preview.png`, `veille.html`, `rss.xml`, `rss/*.xml`, police. Si un fichier manque, rien n'est publié. |
| `deploy/installer_systemd.sh`, `deploy/installer_systemd.fish` | Ancienne installation FTP depuis le PC (obsolète). |
| `bin/gauchiasses-veille.service`, `bin/gauchiasses-veille.timer` | Modèles des unités systemd (lancent `publier_public.py` toutes les 30 min). |
| `bin/requirements.txt` | Dépendances Python de la veille. |
| `venv/` | Environnement Python, créé à l'installation (non versionné). |
| `old/` | Sauvegardes et anciens fichiers, non synchronisés (par ex. `index_849_cartes.html`, l'ancienne page complète). |
| `bin/construire_cartes.py` | Construit les cartes et le nuage de catégories dans `index.html`, à partir des fichiers texte. Tourne sur le PC. |
| `listes/` | Fichiers texte source des cartes (`Vipex.txt`, `On en veut pas !.txt`, `Plus jamais ça !.txt`, `SirClap.txt`, `Kadaj.txt`, `Zaza.txt`). Lus par `construire_cartes.py`. |
| `data/cache/` | Caches du build des cartes et de la veille (aperçus, Twitch), rapport du dernier build. Non synchronisés. |
| `fonts/` | Police des titres (`russo-one.woff2`) et sa licence. Copiée dans `public/` à la publication. |
| `preview.png` | Image d'aperçu (1200×630) affichée quand on partage un lien (Discord, réseaux sociaux), pour `index.html` et le KiosKe (`veille.html`, balises ajoutées dans `bin/build_site.py`). Copiée dans `public/` à la publication. |
| `apercu/preview.svg` | Source de `preview.png`. Pour la régénérer : `rsvg-convert -w 1200 -h 630 apercu/preview.svg -o preview.png` |
| `img/` | Images locales copiées par le build des cartes (si une liste en utilise). |
| `export/` | Copie locale de contrôle du projet (ce qui part sur le serveur). Non synchronisé. |
| `redirections/` | Dossiers des domaines alternatifs (`gauchiasse.org`, `gauchiasses.org`), vides. |

## Éléments immuables

Dans `index.html`, la zone entre `<!-- IMMUABLE:DEBUT -->` et `<!-- IMMUABLE:FIN -->` contient :
la cagnotte, les 3 cartes côte à côte, le lien vers la veille, le lien Discord et le code de conduite.

Aucun build ne doit modifier ce bloc.

```bash
python3 bin/garde_immuable.py verifier      # échoue si le bloc a changé
python3 bin/garde_immuable.py enregistrer   # accepte la version actuelle (après une modif voulue à la main)
```

Un build qui écrit `index.html` doit appeler `verifier_zone()` (dans `bin/garde_immuable.py`) avant et après son écriture.
Le build des cartes (`bin/construire_cartes.py`) écrit entre ses propres marqueurs, et vérifie ce bloc avant et après l'écriture.

## Veille automatique

Taille du KiosKe : sur grand écran (1100 px et plus), le panneau, les tuiles des sources et les fenêtres de catégorie sont agrandis de 25 % (`zoom: 1.25` dans `bin/build_site.py`, règle `@media (min-width: 1100px)`). Les fenêtres de catégorie passent alors à trois colonnes. Sur petit écran, rien ne change.

Génère une page statique de veille (articles RSS et vidéos Twitch) avec titre, source, date,
extrait et aperçu, dans `veille.html`. Les articles sont regroupés par source dans des sections
repliables. La page ne contient aucun JavaScript et reprend le style de la page principale.

**Taille des cartes de la veille** : 75 % de l'ancienne taille. La règle `.carte` de `bin/build_site.py` fixe la largeur à 75 % de la case, et toutes les valeurs internes (textes, marges, bouton « + ») sont réduites du même facteur, pour que rien ne sorte de la carte. Le même CSS s'applique aux cartes des fenêtres de catégorie.

**Lisibilité** : les panneaux et les cartes sont opaques (pas de translucidité ni de flou). Les textes courants (titres d'articles, noms de sources, descriptions) n'ont pas de halo lumineux ; seuls les titres principaux et les étiquettes gardent leur effet. Ce réglage est dans le CSS de `bin/build_site.py` (veille) et dans `style_html` de `bin/construire_cartes.py` (page principale).

### Installation

Le dossier fournit `bin/requirements.txt` (`feedparser`, `yt-dlp`, `legacy-cgi`).
Créer un environnement virtuel et installer les dépendances :

```bash
python3 -m venv venv
venv/bin/pip install -r bin/requirements.txt
```

Les commandes ci-dessous utilisent `venv/bin/python`, à la racine du projet.
Le reste du dossier n'utilise que la bibliothèque standard.

### Construire la page

En local, le venv du projet est `venv_blog/` (`venv_blog/bin/python`). Sur le serveur, c'est `venv/`.

```bash
venv/bin/python bin/build_site.py                 # tous les articles de chaque flux RSS
venv/bin/python bin/build_site.py --no-twitch     # RSS seulement
venv/bin/python bin/build_site.py --no-previews   # sans visiter les pages (rapide)
venv/bin/python bin/build_site.py --no-cache      # ignorer les caches
venv/bin/python bin/build_site.py --nom veille.html
venv/bin/python bin/build_site.py -rss autres_flux.txt -tw autres_chaines.txt
```

- `-rss` : fichier des flux RSS. Par défaut `RSS_feeds.txt`.
- `-tw` : fichier des chaînes Twitch. Par défaut `Twich_feeds.txt`.
- `--nom` : nom du fichier HTML produit. Par défaut `veille.html`.

### Publier

Il n'y a plus d'envoi FTP depuis le passage au serveur (`bin/publish_site.py` a été retiré du projet). La publication se fait sur le serveur, par `bin/publier_public.py` : voir [Déploiement sur le serveur](#déploiement-sur-le-serveur).

### Sources et réglages locaux

`flux_corrige_main.txt` agit sur la veille seulement. Une ligne par réglage, avec une URL identique à
celle de `RSS_feeds.txt`. Les lignes qui commencent par `#` sont des commentaires ; **pas de commentaire
en fin de ligne**, il ferait partie du nom ou casserait la ligne :

```text
!"https://paris-luttes.info/spip.php?page=backend"
"https://www.mediapart.fr/journal/podcasts/rss" | Mediapart (podcasts)
```

Le renommage ne vaut que pour les flux RSS, pas pour les chaînes Twitch.

### Catégories de la veille

Dans `RSS_feeds.txt` et `Twich_feeds.txt`, une ligne `[Nom]` seule ouvre une catégorie. Les flux
ou chaînes qui suivent y vont, jusqu'à la ligne `[…]` suivante. Une source placée avant tout
crochet, ou absente de ces fichiers, tombe dans le bloc « Des Liens » (toujours en dernier).

```text
[Médias d'enquête]
"https://portail.basta.media/spip.php?page=backend"
"https://api.blast-info.fr/rss.xml"
[Twitch]
"ostpolitik"
```

- La page affiche un bloc par catégorie, dans l'ordre du fichier, avec ses étiquettes.
- Une source qui apparaît dans deux catégories garde la première.
- Les étiquettes sont regroupées par URL (ou par nom de chaîne Twitch), et non plus par nom
  affiché : un flux renommé n'apparaît plus deux fois. Son nom affiché est celui de son article le plus récent.
- Sans aucune ligne `[…]`, toutes les sources sont dans le seul bloc « Des Liens ».
- `rss.xml` (le KiosKe entier) n'est pas filtré par catégorie : il ne change pas. Chaque catégorie a son propre flux, voir « Flux RSS par catégorie » plus bas.

Les listes `RSS_feeds.txt` et `Twich_feeds.txt` sont des copies. Si tu modifies celles du bot,
recopie-les ici.

### Historique (SQLite)

Chaque build enregistre les articles récupérés dans `historique.db` (table `articles`).
Rien n'est effacé automatiquement : un article déjà vu reste en base, et sa date de première
apparition est conservée (`premier_vu`).

La table contient :
- `summary` : extrait tronqué (280 caractères) pour l'affichage en page ;
- `content` : texte complet (non tronqué) pour le flux RSS.

La page n'affiche que les articles des sources **encore listées** (`RSS_feeds.txt`,
`Twich_feeds.txt`, sans les lignes ignorées dans `flux_corrige_main.txt`). Retirer une ligne cache
donc ses articles sur le site, sans les effacer de la base : les remettre est une simple
réinsertion de la ligne.

Un flux injoignable au moment du build ne fait rien disparaître : ses articles déjà en base
restent affichés.

Pour repartir de zéro, supprimer `historique.db`.

### Caches

Dans `data/cache/` (non synchronisé) :
- `previews_cache.json` : titre, description et image des pages (Open Graph).
- `twitch_cache.json` : titre, date, durée et miniature des vidéos Twitch.

Un article ou une vidéo déjà connu n'est pas réinterrogé. Supprimer un cache, ou lancer avec
`--no-cache`, force une nouvelle récupération.

### Icône (favicon)

`favicon.svg` est une pluie matricielle sur fond noir, aux couleurs du thème (tête violette, traînée rouge), utilisée dans l'onglet des deux pages. `apple-touch-icon.png` (180×180) est la même icône pour l'écran d'accueil des téléphones. Les deux sont déclarés dans l'en-tête de `index.html` et de `veille.html`. Pour régénérer le PNG : `rsvg-convert -w 180 -h 180 favicon.svg -o apple-touch-icon.png`. La couleur de la barre du navigateur (`theme-color`) reste noire.

### Flux RSS

La page d'accueil (`index.html`) affiche une icône RSS « Flux RSS du KiosKe » sous le bouton « Qui sommes-nous ». Elle est écrite à la main, hors zone générée. Son icône suit la palette ; son libellé reste blanc.

`bin/build_site.py` écrit `rss.xml` à côté de `veille.html` : les 100 articles les plus récents du KiosKe, au format RSS 2.0. L'adresse publique est `https://gauchiasses.fr/rss.xml`. La page KiosKe déclare ce flux dans son en-tête, pour que les lecteurs de flux le trouvent.

Chaque article inclut son **corpus complet** (non tronqué) dans la balise `<description>`, pour qu'il s'affiche entièrement dans les lecteurs RSS (Akregator, Thunderbird, etc.) sans avoir besoin de cliquer sur un lien externe.

Les dates (`pubDate`, `lastBuildDate`) sont données à l'heure de Paris (Europe/Paris, heure d'hiver ou d'été), au format RFC 822 que demande RSS. `publier_public.py` copie `rss.xml` dans `public/`.

### Flux RSS par catégorie

Chaque catégorie de la veille (un bloc titré dans `veille.html`) a son flux RSS, à l'adresse
`https://gauchiasses.fr/rss/<nom>.xml` (par ex. `rss/medias-d-enquete.xml` pour « Médias d'enquête »).
Le nom vient du titre de la catégorie, sans accents ni espaces (`slug_categorie` dans `bin/build_site.py`).

- Le lien est une petite icône RSS aux couleurs du drapeau trans, dans le coin haut-droit du bloc de la
  catégorie. Elle est écrite par `bin/build_site.py` (`ICONE_RSS`, style `.rss-categorie`).
- Chaque flux contient les articles des sources de sa catégorie, au même format que `rss.xml` (corpus complet,
  100 articles maximum). Les sources sans catégorie sont dans `rss/des-liens.xml`.
- Les flux sont écrits dans `rss/` à chaque build. Un flux dont la catégorie a disparu est supprimé.
- `veille.html` déclare aussi chaque flux dans son en-tête, pour les lecteurs qui détectent les flux d'une page.
- `bin/publier_public.py` copie `rss/*.xml` dans `public/rss/`.

### Lien depuis la page principale

`index.html` contient un lien vers `veille.html` dans le bloc immuable. `veille.html` doit être publié
à côté de `index.html` : c'est le cas avec `publier_public.py`.

En retour, `veille.html` a un bouton « ← Retour au site » en haut, qui pointe vers `index.html`
(généré par `bin/build_site.py`, classe `.retour`).

## Build des cartes

Le build construit les cartes et le nuage de catégories dans `index.html`, à partir de fichiers texte. Il tourne **sur le PC**, jamais sur le serveur. Le serveur ne reçoit que le résultat, avec le reste du projet.

### Fichiers utilisés

| Élément | Emplacement |
| --- | --- |
| Listes (fichiers texte) | `listes/*.txt` (aujourd'hui : `Vipex.txt`, `On en veut pas !.txt`, `Plus jamais ça !.txt`, `SirClap.txt`) |
| Anciennes listes | `~/zarisse.fr/listes/archive/` (hors du projet, non utilisées par le build) : les 13 listes précédentes |
| Script | `bin/construire_cartes.py` |
| Caches et rapport | `data/cache/` (`cache_wikipedia.json`, `cache_images.json`, `rapport_cartes.txt`) |
| Page modifiée | `index.html`, à la racine |
| Images locales | `img/`, à la racine |
| Police | `fonts/russo-one.woff2` |

### Format des fichiers texte

Le script accepte **deux formats**, mélangeables dans un même fichier. Les lignes qui commencent par `#` sont ignorées.

**1. Format copié-collé** : tu copies directement une catégorie depuis un autre outil. Le titre est suivi de `N cartes` (le nombre n'est pas utilisé), puis, pour chaque carte, le nom sur une ligne, la description sur la suivante, et une rareté facultative (`Commune`, `Rare`, `Inhabituelle`, `Épique`, `Exceptionnelle`, `Légendaire`, `Mythique`), ignorée à l'affichage. Les raretés sont ignorées partout où elles apparaissent. La liste est dans `RARETES` de `bin/construire_cartes.py` : à compléter si une nouvelle rareté apparaît :

```text
Vipex🚩
19 cartes
Marc Bloch
historien et résistant français
Mythique
Che Guevara
révolutionnaire marxiste et internationaliste argentin
Légendaire
```

Un emoji en fin de titre passe en tête à l'affichage : « Vipex🚩 » donne « 🚩Vipex », comme le format wikipick.

**2. Format wikipick** : un titre de catégorie seul sur sa ligne (un chiffre, le titre, puis le nombre entre parenthèses, le chiffre et le nombre ne sont pas affichés), et des cartes en gras. Les blocs sont séparés par une ligne vide. La ligne `image:` est facultative.

```text
5🚩Vipex (19)

**Marine Le Pen**
femme politique française
image: https://fr.wikipedia.org/wiki/Fichier:Exemple.jpg
```

Ici, la catégorie s'affiche « 🚩Vipex » (emoji au début).

Les lignes `image:` ne sont possibles que dans le format wikipick. Formes acceptées pour `image:` :

| Forme | Effet |
| --- | --- |
| `image: photos/nom.jpg` | Fichier local, relatif au fichier texte. Copié dans `img/`. |
| `image: Fichier:Nom.gif` ou `image: File:Nom.jpg` | Fichier Wikimédia : URL, auteur et licence récupérés. |
| `image: https://fr.wikipedia.org/wiki/Fichier:…` (ou `commons.wikimedia.org/wiki/File:…`) | Idem, à partir du lien de la page du fichier. |
| `image: https://…` | URL d'image directe, sans crédit automatique. |
| (absent) | Image principale de l'article Wikipédia, sinon l'initiale. |

Une ligne qui ne correspond à aucun des deux formats arrête le build avec son numéro : `format non reconnu`.

**Image automatique depuis l'article.** Si Wikipédia ne donne pas d'image principale pour un article, le build prend l'image déclarée dans son infobox (paramètre `image =`). Une ligne `image:` dans le fichier texte reste prioritaire. La licence d'un fichier Commons « Public domain » est affichée « Domaine public », avec l'auteur indiqué sur Commons.

Le cache des pages Wikipédia est passé en version 5 (repli sur le paramètre `logo =` de l'infobox) : le prochain build redemande les 62 noms (environ 3 minutes).

Le nom d'une carte doit correspondre à une page de fr.wikipedia.org. Les pages absentes et les pages d'homonymie sont exclues ; si une carte manque, vérifie son nom (ou utilise le titre exact de l'article) puis relance le build.

### Lancer le build

```bash
cd ~/gauchiasses.fr
python3 bin/construire_cartes.py listes/*.txt
```

Options :

| Option | Effet |
| --- | --- |
| `--hors-ligne` | N'interroge pas Wikipédia, utilise seulement les caches. |
| `--periode=SECONDES` | Période du passage au rouge des puces du nuage (défaut `5`). |
| `--police="Nom"` | Police des titres (défaut `Russo One`). Demande le fichier `fonts/<nom-en-minuscules-avec-tirets>.woff2`. |

Premier build, ou après une modification des versions de cache : environ 3 minutes (une requête par nom et par fichier image, avec une pause d'une seconde). Les builds suivants prennent quelques secondes. Si Wikipédia limite le débit (HTTP 429), le script attend et réessaie tout seul. Les caches sont sauvegardés à chaque lot : une interruption ne perd rien.

Le script écrit entre deux marqueurs, sans toucher au bloc immuable :
- `NUAGE-TAGS` (style et nuage des catégories), juste avant le bloc immuable ;
- `CARTES-TEXTE` (fenêtres de catégories et cartes), après le bloc immuable.

Le bloc immuable est vérifié avant et après l'écriture. Relancer le script remplace les blocs précédents.

Chaque carte a un bouton « + » qui ouvre une fiche avec l'extrait complet et toute la licence de l'image.

### Workflow avant synchronisation

1. Modifier les listes dans `listes/`.
2. Lancer le build (commande ci-dessus).
3. Lire `data/cache/rapport_cartes.txt` : pages absentes, homonymies, doublons.
4. Revérifier le bloc immuable : `python3 bin/garde_immuable.py verifier`.
5. Ouvrir `index.html` dans un navigateur : nuage, fenêtres, boutons « + », cartes du site, bouton « Qui sommes-nous ».
6. Simuler puis synchroniser, avec la fonction fish : `gauchiasses_update --dry-run`, puis `gauchiasses_update` (voir [Déploiement](#déploiement-sur-le-serveur)). `deploy/synchroniser.sh` est l'ancien workflow et n'est plus utilisé.
7. Publier : sur le serveur, `sudo systemctl start gauchiasses-veille.service` (ou attendre le timer, toutes les 30 minutes). Vérifier ensuite que `public/index.html` a la même somme de contrôle que `index.html`.

### Texte « Qui sommes-nous »

Le message « Découvre les collections des membres » est écrit à la main dans `index.html`, juste avant la zone `NUAGE-TAGS`. Il est hors zone générée : le build ne le modifie pas. Il s'affiche au-dessus des étiquettes de collections.

Le bouton et le panneau sont écrits à la main dans `index.html`, entre `QUI-SOMMES-NOUS:DEBUT` et `QUI-SOMMES-NOUS:FIN`. Le build ne touche pas à cette zone : modifie le texte directement là.

### Messages d'erreur fréquents

| Message | Solution |
| --- | --- |
| `bloc sans nom en gras ni titre de catégorie` | Ajouter le `**` au nom, ou vérifier la ligne vide avant le bloc. |
| `image introuvable : …` | Corriger le chemin, relatif au fichier texte. |
| `URL refusée (http, pas https)` | Utiliser `https://`. |
| `HTTP 429` | Rien à faire : le script attend et réessaie. Sinon, relancer plus tard. |
| `absent(s) du cache, refusés (--hors-ligne)` | Relancer sans `--hors-ligne`, avec une connexion. |
| `le bloc immuable a été modifié` | Ne pas modifier le bloc immuable à la main. Le restaurer depuis une copie. |
| `section « cartes » introuvable` | Vérifier que `index.html` est bien la page principale. |

### Réglages

Pluie de fond (CSS pur, dans `index.html` et `bin/build_site.py`) : un seul thème fixe, sans animation de couleur. Quatre couleurs, définies sur `:root` : violet en tête (`--r-tete`, `#8f00ff`), rouge (`--r-haut`, `#ff1a1a`), rose foncé (`--r-moyen`, `#b5179e`) et bleu-violet en queue (`--r-bas`, `#4b3fd8`). Les bordures et les étiquettes restent blanches ; les cadres des cartes restent rouges, et seule l'étiquette clignote en rouge. La vitesse de chute est réglée par les durées d'animation des colonnes (sur la page principale : `animation-duration` des éléments `<i>` de `#pluie` ; dans le KiosKe : `rnd.uniform(3.6, 9.6)` dans `rain()`).

Images des cartes : la carte garde sa taille fixe, et l'image est réduite pour tenir entièrement dedans (`object-fit: contain`, fond sombre autour), sans recadrage ni zoom. Le réglage est dans le CSS de `bin/construire_cartes.py`.

Étiquettes : la page principale n'a plus de réduction (`zoom`) sur son panneau. Les étiquettes du nuage ont ainsi la même taille et le même rendu que sur le KiosKe (`--puce-taille`, police Russo One).

- Dans le bloc CSS généré (entre `NUAGE-TAGS`), les variables `:root` contrôlent les couleurs, les tailles des puces, des fenêtres et des cartes. Elles sont réécrites à chaque build : pour les garder, modifie la fonction `style_html` dans `bin/construire_cartes.py`.
- Dans `bin/construire_cartes.py` : `VERSION_CACHE` et `VERSION_FICHIERS` forcent une nouvelle récupération quand on les incrémente ; `TAILLE_LOT` et `PAUSE` règlent le rythme des requêtes.

## Ancienne publication FTP (obsolète)

Les anciennes publications en FTP (construction sur le PC, envoi par `bin/publish_site.py`) sont obsolètes. Le site est maintenant servi par le serveur, voir [Déploiement sur le serveur](#déploiement-sur-le-serveur).

### Ancien installateur systemd (FTP)

Sur la machine de destination, dans le dossier du projet :

```bash
./deploy/installer_systemd.sh                 # installe et active le timer (sudo demandé)
./deploy/installer_systemd.sh --desinstaller  # arrête et supprime le service et le timer
# En fish, le même script existe : ./deploy/installer_systemd.fish (mêmes options)
```

Le script installe `python3` et `python3-venv` si besoin, crée `venv/` et y installe
`bin/requirements.txt`, restreint `bin/publish_site.py` au propriétaire (`chmod 600`, il contient le mot
de passe FTP), puis installe `gauchiasses-veille.service` et `gauchiasses-veille.timer` dans
`/etc/systemd/system`. Le timer lance la publication 2 minutes après le démarrage, puis toutes les
30 minutes.

Suivi :

```bash
systemctl list-timers gauchiasses-veille.timer
journalctl -u gauchiasses-veille.service -n 50
sudo systemctl start gauchiasses-veille.service   # lancer une publication tout de suite
```

## Déploiement sur le serveur

Le site est construit et servi par le serveur perso (Debian 13, nginx). Le projet vit dans
`/home/meli/gauchiasses.fr`, et la racine servie est `public/`.

### Depuis ton PC : copier le projet

Utilise la fonction fish `gauchiasses_update` (définie dans `~/.config/fish/functions/gauchiasses_update.fish`) :

```bash
gauchiasses_update --dry-run    # vérifie ce qui serait synchronisé
gauchiasses_update              # synchronise vers meli@zarisse.fr:/home/meli/gauchiasses.fr/
```

La fonction utilise `rsync` avec `--delete` pour nettoyer le serveur de ce qui a été supprimé localement.

**Fichiers synchronisés** : `index.html`, `favicon.svg`, `apple-touch-icon.png`, `veille.html`, `rss.xml`, `rss/` (régénéré par le build sur le serveur), listes (`listes/*.txt`), flux (`RSS_feeds.txt`, `Twich_feeds.txt`, `flux_corrige_main.txt`), scripts (`bin/*.py`), données persistantes (`data/immuable.json`, `data/historique.db`), fontes (`fonts/`), images (`img/`).

**Fichiers et dossiers exclus** : `.claude/`, `apercu/`, `docs/`, `redirections/`, `venv/`, `venv_blog/`, `data/cache/`, `public/`, `old/`, `export/`, `.git/`, `CLAUDE.md`, `preview.png`, `bin/sauvegarde_logs.sh`, et fichiers temporaires (`*.swp`, `.DS_Store`).

> **Point ouvert** : `preview.png` est exclu de la synchronisation, mais `bin/publier_public.py` en a besoin pour le publier. Sur le serveur, la publication s'arrête alors avec `Fichier absent, rien publié` et ne copie rien (ni `index.html`, ni la veille). Il faut retirer `preview.png` des exclusions de `gauchiasses_update`, ou le copier à part sur le serveur.

### Sur le serveur : installer

```bash
cd /home/meli/gauchiasses.fr
./deploy/installer_serveur.sh          # ou ./deploy/installer_serveur.fish
./deploy/installer_serveur.sh --desinstaller
```

L'installation crée le venv, prépare `public/` et `data/`, installe le timer systemd et lance
une première publication. Chaque passage (toutes les 30 min) :
1. reconstruit la veille à partir des flux, et ajoute les nouveaux articles à `data/historique.db` ;
2. vérifie le bloc immuable de `index.html` ;
3. copie `index.html`, `favicon.svg` et `veille.html` dans `public/`.

Si le bloc immuable a été modifié, la page principale n'est pas publiée et le journal l'indique.

### Suivi

```bash
systemctl list-timers gauchiasses-veille.timer
journalctl -u gauchiasses-veille.service -n 50
sudo systemctl start gauchiasses-veille.service   # publier tout de suite
```

### Vérifier la mise en ligne

Sur le serveur, `./deploy/verifier_serveur.sh` contrôle le DNS, nginx, les pages en HTTPS, le certificat et son
renouvellement, les timers et la date de la dernière publication. Il affiche ce qui reste à vérifier à la main.
Avec `--externe`, il teste aussi l'accès via l'IP publique (à lancer depuis l'extérieur de ton réseau).

### nginx et DNS

Sur le serveur, nginx est configuré par `deploy/deployer_nginx.sh` :

```bash
./deploy/deployer_nginx.sh --email toi@exemple.fr   # HTTP puis HTTPS (Let's Encrypt)
./deploy/deployer_nginx.sh --sans-certificat        # HTTP seulement
./deploy/deployer_nginx.sh --desinstaller           # retire le site (certificats conservés)
```

Le certificat couvre `gauchiasses.fr` seul : `www.gauchiasses.fr` n'a pas d'enregistrement DNS. Pour l'ajouter, crée d'abord le DNS, puis adapte le script.

Le script écrit `/etc/nginx/sites-available/gauchiasses.fr`, teste la configuration, et la remet
en place si elle est invalide. Il ne touche pas aux autres sites (ex. `blog.zarisse.fr`).

Le bloc HTTPS a les mêmes protections que `kioske.fr` : HSTS, `nosniff`, `X-Frame-Options`,
`Referrer-Policy`, `Permissions-Policy`, `server_tokens off`, méthodes GET et HEAD seulement (405),
fichiers cachés refusés (404). Politique de contenu : `script-src 'self'` (le site n'a pas de
JavaScript), `img-src 'self' data: https:` (images de n'importe quelle source HTTPS). En-têtes
répétés dans `/veille/`, car une `location` avec son propre `add_header` efface ceux du bloc `server`.

Étapes : HTTP seul d'abord, puis certificat, puis HTTPS. Le certificat n'est demandé que si
`gauchiasses.fr` pointe vers l'adresse du serveur. Sinon le site reste en HTTP, et il suffit de
relancer le script une fois le DNS mis à jour.

Prérequis : nginx doit pouvoir lire `public/`. Si le script le signale, il faut autoriser la
traversée du dossier home (`chmod o+x /home/meli`). Ce changement est à valider par toi.

Page « Tu es banni » : chaque bloc `server` inclut `/etc/nginx/snippets/fail2ban-banni.conf`
(comme les autres sites), ce qui permet à fail2ban de bannir une IP sur ce site. Le fichier est
créé sur le serveur par `fail2ban_hardened/f2b.sh`. Si le fichier n'existe pas encore, le script
n'inclut rien et l'affiche : lance alors `sudo bash fail2ban_hardened/f2b.sh /etc/nginx/sites-available/gauchiasses.fr`,
puis relance le déployeur. Sans ce fichier, nginx refuserait la configuration.

`deploy/nginx-gauchiasses.conf` est une référence de l'ancienne version, remplacée par le script.

## Redirections (domaines alternatifs)

Les domaines `gauchiasse.org` (singulier) et `gauchiasses.org` (pluriel) redirigent tous deux vers `gauchiasses.fr` en HTTPS, en préservant l'URI (ex. `gauchiasse.org/foo` → `https://gauchiasses.fr/foo`).

### Déploiement

Le script de déploiement vit dans `~/Lenovo_scripts/redirections_gauchiasses.sh` (créé en session 2026-11-10).

Sur le serveur, en root :

```bash
sudo bash /tmp/redirections_gauchiasses.sh
```

Le script :
1. Crée deux fichiers nginx dans `/etc/nginx/sites-available/` (un par domaine) ;
2. Active les sites (liens symb. dans `sites-enabled/`) ;
3. Génère les certificats SSL avec certbot (si nécessaire) ;
4. Teste la configuration nginx ;
5. Recharge nginx.

Chaque bloc nginx écoute sur HTTP et HTTPS, avec redirection HTTP → HTTPS, puis redirection HTTPS vers `https://gauchiasses.fr`.

Vérification après déploiement :

```bash
curl -I http://gauchiasse.org      # doit rediriger en 301
curl -I https://gauchiasse.org     # doit rediriger vers https://gauchiasses.fr en 301
curl -I http://gauchiasses.org     # même comportement
```

## Mise en ligne (ancienne méthode FTP)

Envoyer en FTP :
- `index.html` et `favicon.svg` ;
- `veille.html` si la veille est utilisée.

Ne pas envoyer : `bin/`, `data/`, `deploy/`, `old/`, les fichiers de flux et `flux_corrige_main.txt`.

## SEO et mots-clefs

Le site cible les mots-clefs : **gauchiasses**, **gauche**, **Mélenchon**, **2027**, **votez**, **La France insoumise**.

### Optimisations appliquées

- **Header enrichi** : title, descriptions meta et Open Graph incluent les mots-clefs naturellement.
- **Keywords meta** : balise dédiée aux termes ciblés pour les moteurs de recherche.
- **Structured data (schema.org)** : données structurées au format JSON-LD pour identifier le site comme une organisation politique de gauche.
- **Alt des images** : les 3 cartes principales (Mélenchon, Rima Hassan, La France insoumise) ont désormais des descriptions alt pertinentes pour l'accessibilité et le SEO.

### Bloc immuable et SEO

Les alt des images du bloc immuable (entre `<!-- IMMUABLE:DEBUT -->` et `<!-- IMMUABLE:FIN -->`) ont été modifiées le 2026-11-10 pour améliorer le SEO. L'empreinte du bloc a été enregistrée dans `data/immuable.json`.

## Limites et sécurité

- **Mot de passe FTP en clair** dans `bin/publish_site.py`. Ne publie pas ce fichier avec le vrai mot
  de passe. Préfère FTPS quand c'est possible.
- **Réseau local** : Chrome demande l'accès au réseau local si la page charge une ressource
  dont le nom se résout en adresse privée. Par exemple, `blog.zarisse.fr` se résout en
  `192.168.1.13` sur la machine de développement. Ne mets pas de flux ou d'image de ce type
  dans la veille.
- Un flux injoignable est ignoré avec un message `[flux] …` ; la page est construite sans lui.
- Twitch passe par yt-dlp. Une vidéo invalide (abonnés seulement, supprimée…) est ignorée avec un message `[twitch] … vidéo … ignorée` ; les suivantes de la même chaîne restent affichées. Une chaîne sans aucune vidéo accessible ne produit aucune carte.
- Les aperçus viennent de la page de l'article ; certains sites ne fournissent pas d'image.

## Licences

Textes : Wikipédia, CC BY-SA 4.0. Images : Wikimedia Commons ou Wikipédia, auteur et licence
indiqués sur la page du fichier, liée depuis chaque fiche. Articles de veille : leurs auteur.ice.s
et sites respectifs.
