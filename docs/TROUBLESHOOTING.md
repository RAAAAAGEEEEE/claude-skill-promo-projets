# Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| `ERREUR ... champ obligatoire vide ou absent` | fiche incomplète | compléter le champ cité ([CONFIGURATION.md](CONFIGURATION.md)) |
| `ERREUR fait sans source` | un `faits` sans `\| https://...` | ajouter la source ou retirer le fait |
| `ERREUR communauté r/X revendiquée par A et B` | même sub dans deux fiches | garder la communauté dans un seul projet |
| `scan` ne lit aucun flux, rapport « à lire d'abord [NV] » | règles non enregistrées | lire l'onglet Règles puis `promo.py rules` |
| `AVERTISSEMENT HTTP 429` | Reddit limite les lectures anonymes | attendre quelques minutes ; ne pas réduire le délai de 65 s |
| `r/X illisible (statut 403)` | Reddit refuse la requête | relancer plus tard ; sinon enregistrer le fil à la main avec `--from-feed` |
| `discover` : « archive illisible » | Arctic Shift injoignable ou sub inconnu | relancer ; la taille reste « inconnu » |
| `check-reply` FAIL « plafond ou règle » | lien non permis | retirer le lien, ou attendre que `stats` annonce « prochain lien possible : oui » |
| `check-reply` FAIL « quasi identique » | réponse proche d'une autre | réécrire pour ce fil précis |
| `send` : variables manquantes | Telegram non configuré | définir `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` ([CONFIGURATION.md](CONFIGURATION.md)) |
| accents illisibles dans le terminal Windows | codage de la console | la sortie est forcée en UTF-8 ; utiliser Windows Terminal |

Aucune ligne du ledger ne se supprime par commande : corriger `ledger.csv` à la main (fichier CSV simple) en
gardant l'en-tête.

## Voir aussi

[Usage](USAGE.md) · [Limites](LIMITATIONS.md)
