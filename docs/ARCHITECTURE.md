# Architecture

```text
SKILL.md                 procédure suivie par Claude Code
scripts/promo.py         interface en ligne de commande (argparse)
scripts/promo_core/
  miniyaml.py            en-tête de fiche (sous-ensemble minimal de YAML)
  project.py             fiches, validation, une communauté = un projet
  relevance.py           score par mots-clés (mots entiers, accents ignorés)
  state.py               règles lues, ledger CSV, règle du lien
  scan.py                rotation, répartition des fils, rapports Markdown
  checkreply.py          contrôles mécaniques d'une réponse
  telegram.py            envoi optionnel
  channels/reddit.py     flux RSS, archive Arctic Shift, mesure des communautés
canaux/                  contrat d'un canal et canaux à venir
examples/projets/        fiches fictives
tests/test_promo.py      51 tests, réseau simulé
```

## Flux

1. `discover` : recherche RSS de communautés, puis mesure dans l'archive (abonnés, cadence, part de fils sur
   le sujet, colonne latérale). Écrit un rapport, ne modifie aucun état.
2. `rules` : seule porte d'entrée d'une communauté dans `communautes.json`, avec citation obligatoire.
3. `scan` : pour chaque communauté lue, un flux de recherche ; score ; `plan()` répartit les fils par rotation
   (le projet resté le plus longtemps sans contribution passe en premier), un tour par projet, un fil à un seul
   projet, au plus un lien autorisé par passe ; propositions écrites au ledger ; rapport.
4. `check-reply` : contrôle une réponse avec la politique de sa communauté et le ledger, met à jour `has_link`.
5. `mark` / `log` : l'humain déclare ce qu'il a publié.

## Décisions de conception

- Le code ne contient aucun appel d'écriture vers Reddit ; les seules requêtes sortantes sont des GET.
- Le ledger compte les propositions : le plafond est calculé sur le pire cas.
- Les modèles ne sont pas appelés par le script : la rédaction en 3 passes est faite par Claude Code selon
  `SKILL.md`, ce qui garde le script gratuit, testable hors ligne et sans clé.
- Réseau injectable (`fetch`, `sleep`) pour tester sans accès Internet.

## Voir aussi

[Canaux](../canaux/README.md) · [Configuration](CONFIGURATION.md) · [Limites](LIMITATIONS.md)
