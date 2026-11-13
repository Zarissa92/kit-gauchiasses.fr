"""gauchiasses : le site gauchiasses.fr. Site statique, HTML5 et CSS, sans JavaScript.

Deux pages : la page principale (accueil/index.html, écrite à la main, avec son bloc immuable et ses
cartes Wikipédia) et le KiosKe (veille.html, veille automatique des flux RSS et des chaînes Twitch).

Modules : config (chemins, gauchiasses.cfg), sources, flux, twitch, apercus, images, historique,
themes, rendu, rss, cartes, immuable, verrou, construction, publication.
Points d'entrée : bin/build_site.py, bin/publier_public.py, bin/garde_immuable.py, bin/construire_cartes.py.
"""
