# Architecture

```text
SKILL.md                 procédure suivie par Claude Code
scripts/promo.py         interface en ligne de commande (argparse)
scripts/promo_core/
  miniyaml.py            en-tête de fiche (sous-ensemble minimal de YAML)
  project.py             fiches, validation, une communauté = un projet
  relevance.py           score par mots-clés (mots entiers, accents ignorés)
  accounts.py            registre des comptes, éligibilité, bannissements
  ruleflags.py           texte des règles -> drapeaux et politique déduite
  rulesfetch.py          lecture réseau des règles, détection d'une page de vérification
  state.py               règles lues, ledger CSV, règle du lien (par compte), conflits entre comptes
  scan.py                rotation, affectation d'un compte par fil, rapports Markdown
  warmup.py              chauffe : choix des fils, contrôle des brouillons, rédacteur externe optionnel
  daypage.py             page HTML du jour, serveur local, cache des fils
  checkreply.py          contrôles mécaniques d'une réponse de promo
  telegram.py            envoi optionnel
  channels/reddit.py     flux RSS, archive Arctic Shift, mesure des communautés
canaux/                  contrat d'un canal et canaux à venir
examples/projets/        fiches fictives
tests/test_promo.py      tests de base (0.1), réseau simulé
tests/test_forge.py      tests multi-comptes, chauffe, règles, page, serveur, daily (0.2)
```

## Flux

1. `discover` : recherche RSS de communautés, puis mesure dans l'archive. Écrit un rapport, ne modifie aucun état.
2. `rules` : seule porte d'entrée d'une communauté dans `communautes.json` : `fetch` / `import` (texte daté, drapeaux,
   politique déduite) ou `--policy --quote` (phrase lue). Un import n'assouplit jamais une politique posée à la main.
3. `accounts` : registre `comptes.json`. `Registry.eligible` combine affectation, bannissements, karma et âge exigés.
4. `warmup run` : flux `/new.rss` des communautés lues des comptes, `answerable` (question, avis, remerciement),
   sélection par compte (N par jour, M par communauté, tour de rôle entre communautés), lignes `warmup` au ledger sans
   lien. Brouillons dans `chauffe/<date>/`, contrôlés par `check_draft`.
5. `scan` : un flux de recherche par communauté lue ; `plan()` répartit les fils par rotation entre projets, puis
   `_pick_account` choisit un compte éligible sans conflit ; au plus un lien autorisé par passe et par compte.
6. `check-reply` / `warmup check` : contrôles mécaniques ; `check-reply` met à jour `has_link`.
7. `page` / `serve` : `daypage` assemble les lignes du ledger du jour, les titres (`fils.json`) et les brouillons.
8. `ledger add --id` / `mark` / `log` : l'humain déclare ce qu'il a publié.
9. `daily` : 1 à 4 enchaînés, avec des marqueurs `sorties/.AAAA-MM-JJ.*.ok` pour l'idempotence (`--force` les ignore).

## Décisions de conception

- Le code ne contient aucun appel d'écriture vers Reddit ; les seules requêtes sortantes sont des GET.
- Les règles multi-comptes sont dans `state.py` (`Ledger.conflict`, `link_allowed`) et `accounts.py`, appelées par
  chaque chemin qui peut créer une ligne du ledger (scan, chauffe, log) : aucune ne dépend de la bonne volonté du
  rédacteur.
- Le ledger compte les propositions : le plafond est calculé sur le pire cas. La colonne `account` vide désigne
  l'ancien mode mono-compte, resté identique.
- Les modèles ne sont pas appelés par le script (sauf `--drafter`, commande choisie par l'utilisateur) : la rédaction
  est faite par Claude Code selon `SKILL.md`, ce qui garde le script gratuit, testable hors ligne et sans clé.
- Réseau injectable (`fetch`, `sleep`, `drafter`, `post`) pour tester sans accès Internet.
- La page du jour est un seul fichier HTML sans dépendance ; le serveur local est un confort, jamais une obligation.

## Voir aussi

[Canaux](../canaux/README.md) · [Configuration](CONFIGURATION.md) · [Limites](LIMITATIONS.md)
