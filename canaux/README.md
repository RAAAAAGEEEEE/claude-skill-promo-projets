# Canaux

Un canal est un endroit où promouvoir un projet. Chaque canal a un fichier de règles ici et, une fois
implémenté, un module sous `scripts/promo_core/channels/`.

| Canal | État | Fichier |
|---|---|---|
| Reddit | implémenté (lecture seule, publication manuelle) | [reddit.md](reddit.md) |
| Autres | TODO documenté | [TODO.md](TODO.md) |

## Contrat d'un canal

Un canal fournit, sans jamais écrire sur la plateforme :

1. une découverte de lieux (communautés, groupes, listes) avec taille et activité mesurées ;
2. un registre des règles lues, avec citation, avant tout repérage ;
3. un repérage de contenus en lecture seule par une source publique ;
4. des contraintes de format (longueur, liens, mention du lien d'intérêt) contrôlables mécaniquement ;
5. une écriture dans le ledger commun (`ledger.csv`) pour que le plafond de liens reste global.

Le plafond de liens, la rotation et la règle « un fil, un projet » sont communs à tous les canaux : ne pas les
recoder par canal.

## Voir aussi

[Architecture](../docs/ARCHITECTURE.md) · [Contribuer](../CONTRIBUTING.md)
