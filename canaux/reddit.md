# Canal Reddit

Statut : implémenté dans `scripts/promo_core/channels/reddit.py`.

## Sources utilisées (lecture seule)

- Flux RSS publics : recherche de communautés (`/subreddits/search.rss?q=`) et recherche dans une communauté
  (`/r/<sub>/search.rss?q=...&restrict_sr=1&sort=new`). Environ une requête anonyme par minute : le code attend
  65 s entre deux et s'arrête au premier 429.
- Archive publique Arctic Shift : abonnés, date et cadence des 100 derniers fils, colonne latérale archivée.
  Elle ne donne PAS les règles à jour.

## Ce qui n'est pas disponible

L'API de données de Reddit n'est plus en libre-service (approbation préalable). Les pages Reddit et `about.json`
sont bloquées pour les scripts. Conséquence : le texte à jour de l'onglet Règles ne peut être lu que par un
humain (ou un navigateur qu'il pilote), puis enregistré avec `promo.py rules`.

## Règles de conduite appliquées

- Participation réelle d'abord, lien rare : au plus 1 contribution sur 10 avec lien, tous projets confondus.
- Lien toujours déclaré (« je tiens... », « I make... »), jamais de réponse identique d'un fil à l'autre.
- Un seul compte, aucun vote, aucune publication par l'outil.
- Une communauté par projet, un projet par fil.

## Politiques de communauté

`interdit` : aucune autopromotion, participation sans lien seulement. `declaree-ok` : lien permis si déclaré.
`fil-dedie` : lien seulement dans un fil prévu, à traiter à la main. `non-verifie` : règle non lue, `[NV]`.
