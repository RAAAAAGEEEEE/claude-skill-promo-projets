# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versionnement sémantique.

## [0.2.0] - 2026-10-08

### Ajouté
- Multi-comptes : registre `comptes.json` (`accounts add|assign|ban|list`), colonnes `account` et `origin` du ledger,
  règles dures codées (jamais deux comptes dans le même fil ni la même communauté le même jour, jamais de réponse d'un
  compte à un fil d'un autre, bannissement = communauté fermée à tous, ratio de liens tenu par compte).
- Chauffe : `warmup run|check`, brouillons sans lien ni mention de projet, interdits codés (générique, emoji seul,
  doublon, excès par communauté), rédacteur externe optionnel `--drafter`.
- Règles de communauté : `rules fetch` (rules.json puis old.reddit.com, détection d'une page de vérification) et
  `rules import --from-text` ; texte daté et drapeaux (autopromo interdite, ratio imposé, karma et âge minimum, jour
  dédié, fil dédié, liens interdits) respectés par le planificateur.
- Page du jour `page` (HTML sans dépendance : Copier, Ouvrir le fil, Marquer publié) et serveur local `serve`
  (127.0.0.1, jeton par page).
- `ledger add --id` pour inscrire une publication faite à la main ; `daily` (repérage, chauffe, contrôle des réponses de
  promo, page du jour, idempotent, `--telegram` facultatif).

### Modifié
- `link_allowed` prend le compte, les drapeaux et la date ; sans registre de comptes le comportement 0.1 est inchangé.
- `stats` affiche le ratio par compte. `rules` accepte une communauté qui n'appartient à aucun projet si un compte l'a.
- Le corps des réponses HTTP d'erreur est conservé pour reconnaître une page de vérification. User-Agent 0.2.

## [0.1.0] - 2026-10-08

### Ajouté
- Skill `promo-projets` : fiches projet, découverte et mesure de communautés, enregistrement des règles lues,
  repérage de fils par flux RSS publics, ledger commun (plafond 1 sur 10), rotation, un projet par fil,
  contrôles de réponse, rapport Markdown, envoi Telegram optionnel.
- Canal Reddit (lecture seule) ; autres canaux documentés dans `canaux/TODO.md`.
- 51 tests automatiques (bibliothèque standard).
