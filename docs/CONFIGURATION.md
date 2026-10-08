# Configuration

## Variables d'environnement

Toutes facultatives. Modèle sans valeur : [.env.example](../.env.example). Le script ne charge aucun fichier
`.env` : exporter les variables dans le shell ou le planificateur.

| Variable | Rôle | Défaut |
|---|---|---|
| `PROMO_DATA_DIR` | dossier de données de l'utilisateur | `~/.promo-projets` |
| `PROMO_USER_AGENT` | User-Agent déclaré aux requêtes en lecture | `promo-projets/0.1 (lecture seule, aucune publication)` |
| `TELEGRAM_BOT_TOKEN` | jeton du bot, pour `send` | aucun |
| `TELEGRAM_CHAT_ID` | conversation de destination, pour `send` | aucun |

`--data-dir` (option de la commande) l'emporte sur `PROMO_DATA_DIR`.

## Dossier de données

| Chemin | Contenu |
|---|---|
| `projets/<slug>.md` | une fiche par projet |
| `communautes.json` | règles lues : politique, citation, date de lecture, projet |
| `ledger.csv` | contributions : `id,date,project,sub,thread_url,kind,has_link,status,note` |
| `reponses/<id-du-fil>.md` | réponses finales à contrôler |
| `sorties/` | rapports du jour et de découverte |

Ces fichiers contiennent tes données : ne jamais les committer dans le dépôt du skill (`.gitignore` les exclut).

## Fiche projet

Un fichier Markdown dont l'en-tête (entre deux lignes `---`) suit un sous-ensemble minimal de YAML : `clé: valeur`
ou `clé:` suivie de lignes `  - élément`. Le corps libre sert de notes (ton, sujets à éviter). Modèles :
[examples/projets/](../examples/projets/).

| Champ | Obligatoire | Forme |
|---|---|---|
| `nom` | oui | texte |
| `type` | non | site documentaire, jeu vidéo, SaaS... |
| `pitch` | oui | une phrase |
| `public` | oui | à qui s'adresse le projet |
| `liens` | oui | adresses ; la première est le lien à poser |
| `faits` | non, mais sans fait rien n'est affirmable | `fait \| https://source` ; sans source valide, la fiche est refusée |
| `mots_cles` | oui | `mot \| poids \| mode` ; poids entier (2 = fort, 1 = faible), mode `word`, `prefix` ou `regex` |
| `mots_exclus` | non | un de ces mots dans le fil met son score à 0 |
| `langues` | oui | `fr`, `en`... |
| `subs` | oui | noms de communautés, sans `r/` ; une communauté ne figure que dans UNE fiche |
| `mention` | oui | phrases acceptées pour déclarer le lien avec le projet, une par langue |
| `requetes_communautes` | non | requêtes de `discover` ; défaut : les 6 mots-clés les plus lourds |

Un fil est retenu à partir de 2 points. Le nom du fichier est le slug (lettres minuscules, chiffres, tirets).

## Seuils réglables

`--warmup N` (30 par défaut) : contributions sans lien avant le premier lien. `scan --max` (4) : fils par
passe ; `--max-per-project` (2). Les autres seuils (plafond 1 sur 10, 1 400 signes, 500 abonnés minimum, 30
jours d'inactivité maximum, 0,3 fil par jour minimum, 65 s entre deux flux) sont des constantes de
`scripts/promo_core/state.py`, `scan.py` et `channels/reddit.py`.

## Voir aussi

[Usage](USAGE.md) · [Vie privée et sécurité](PRIVACY_AND_SECURITY.md)
