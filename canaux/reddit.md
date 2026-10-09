# Canal Reddit

Statut : implémenté dans `scripts/promo_core/channels/reddit.py`.

## Sources utilisées (lecture seule)

- Flux RSS publics : recherche de communautés (`/subreddits/search.rss?q=`) et recherche dans une communauté
  (`/r/<sub>/search.rss?q=...&restrict_sr=1&sort=new`). Environ une requête anonyme par minute : le code attend
  65 s entre deux et s'arrête au premier 429.
- Règles d'une communauté : `https://www.reddit.com/r/<sub>/about/rules.json`, puis
  `https://old.reddit.com/r/<sub>/about/rules/`, puis la copie archivée
  `https://arctic-shift.photon-reddit.com/api/subreddits/rules?subreddits=<sub>` (`promo.py rules fetch`). La copie
  d'archive est enregistrée avec sa date (`arctic-shift (copie du AAAA-MM-JJ)`) et signalée au-delà de 90 jours. Si rien
  n'est lisible, le texte est lu par le navigateur de l'utilisateur et importé (`promo.py rules import`).
- Derniers fils d'une communauté (`/r/<sub>/new.rss`) pour la chauffe.
- Archive publique Arctic Shift : abonnés, date et cadence des 100 derniers fils, colonne latérale archivée.
  Elle ne donne PAS les règles à jour.

## Ce qui n'est pas disponible

L'API de données de Reddit n'est plus en libre-service (approbation préalable). Les pages Reddit sont souvent bloquées
pour les scripts. Conséquence : `rules fetch` peut échouer ; le texte à jour de l'onglet Règles est alors lu par un
humain (ou un navigateur qu'il pilote) et enregistré avec `promo.py rules import` ou `promo.py rules --quote`.

## Règles de conduite appliquées

- Participation réelle d'abord, lien rare : au plus 1 contribution sur 10 avec lien, tous projets confondus.
- Lien toujours déclaré (« je tiens... », « I make... »), jamais de réponse identique d'un fil à l'autre.
- Comptes que tu possèdes déjà seulement : jamais deux dans le même fil ni la même communauté le même jour, jamais de
  réponse ni de vote de l'un à l'autre, ratio tenu par compte, aucune publication par l'outil.
- Chauffe : brouillons utiles, sans lien ni mention de projet, jamais génériques ni copiés.
- Une communauté par projet, un projet par fil.

## Politiques de communauté

`interdit` : aucune autopromotion, participation sans lien seulement. `declaree-ok` : lien permis si déclaré.
`fil-dedie` : lien seulement dans un fil prévu, à traiter à la main. `non-verifie` : règle non lue, `[NV]`.
