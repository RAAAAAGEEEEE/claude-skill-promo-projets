# Contribuer

1. Ouvrir une issue avant un changement de comportement.
2. Python 3.10+, bibliothèque standard seulement : pas de nouvelle dépendance.
3. Lancer `python -m unittest discover -s tests` : tout doit passer. Un comportement nouveau a son test.
4. Mettre à jour la documentation dans le même commit (`docs/`, `README.md`, `CHANGELOG.md`, `.env.example`
   pour toute variable).
5. Ne documenter qu'une commande réellement exécutée.

## Refusé d'office

Publication ou vote automatiques, multi-compte, contournement de 429 ou 403, grattage de pages, fiches de
projets réels, e-mails ou secrets dans le dépôt.

## Ajouter un canal

Suivre [canaux/README.md](canaux/README.md) : un fichier de règles, un module sous
`scripts/promo_core/channels/`, des tests réseau simulés, une ligne dans le README.
