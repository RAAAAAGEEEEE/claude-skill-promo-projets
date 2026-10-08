# Configuration

## Variables d'environnement

Toutes facultatives. Modèle sans valeur : [.env.example](../.env.example). Le script ne charge aucun fichier
`.env` : exporter les variables dans le shell ou le planificateur.

| Variable | Rôle | Défaut |
|---|---|---|
| `PROMO_DATA_DIR` | dossier de données de l'utilisateur | `~/.promo-projets` |
| `PROMO_USER_AGENT` | User-Agent déclaré aux requêtes en lecture | `promo-projets/0.2 (lecture seule, aucune publication)` |
| `TELEGRAM_BOT_TOKEN` | jeton du bot, pour `send` | aucun |
| `TELEGRAM_CHAT_ID` | conversation de destination, pour `send` | aucun |

`--data-dir` (option de la commande) l'emporte sur `PROMO_DATA_DIR`.

## Dossier de données

| Chemin | Contenu |
|---|---|
| `projets/<slug>.md` | une fiche par projet |
| `comptes.json` | registre des comptes : rôle, projets et communautés affectés, karma, date de création, bannissements |
| `communautes.json` | règles lues : politique, citation, date de lecture, texte des règles importé, source, drapeaux |
| `ledger.csv` | contributions : `id,date,project,sub,thread_url,kind,has_link,status,note,account,origin` (`origin` : promo, warmup, manual) |
| `fils.json` | cache des titres et extraits de fils proposés (500 derniers), pour la page du jour |
| `reponses/<id-du-fil>.md` | réponses de promo finales à contrôler |
| `chauffe/AAAA-MM-JJ/<compte>__<id-du-fil>.md` | brouillons de chauffe du jour |
| `sorties/` | rapports du jour (`.md`), page du jour (`.html`), rapports de découverte, marqueurs `.AAAA-MM-JJ.*.ok` de `daily` |

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

## Comptes

`promo.py accounts add <pseudo> --role <texte> --karma N (--since AAAA-MM-JJ | --age-days N)` crée ou met à jour un
compte ; `accounts assign <pseudo> --projects a,b --subs X,Y` l'affecte ; `accounts ban <pseudo> <sub>` note un
bannissement et ferme la communauté à tous les comptes ; `accounts list` affiche le registre. Pseudo : 3 à 20 lettres,
chiffres, tiret, tiret bas, sans pseudo réel dans le dépôt. Un compte sans `--subs` utilise les communautés de ses
projets pour la chauffe ; sans `--projects`, il peut recevoir n'importe quel projet. Le karma et l'âge ne sont pas lus sur
Reddit : tu les tiens à jour à la main.

## Drapeaux tirés des règles lues

`rules fetch` et `rules import` enregistrent le texte (daté, avec sa source) et en tirent : `autopromo_interdite`,
`liens_interdits`, `fil_dedie`, `jour_autopromo` (0 = lundi), `ratio_fenetre` (1 contribution avec lien sur N),
`karma_min`, `age_min_jours`. Heuristiques en anglais et en français ; le texte intégral reste stocké pour relecture.
Politique déduite : `interdit` (autopromo ou liens interdits), `declaree-ok` (jour dédié ou ratio explicite),
`fil-dedie`, sinon `non-verifie` (aucun lien). Un import n'assouplit jamais une politique posée à la main.

## Seuils réglables

`--warmup N` (30 par défaut) : contributions sans lien avant le premier lien, comptées par compte. `scan --max` (4) :
fils par passe ; `--max-per-project` (2). Chauffe (`warmup run`, `daily`) : `--per-account` (4 par défaut, 1 à 10
acceptés, 3 à 5 conseillés), `--per-sub` (2). Brouillon de chauffe : 15 mots et 90 signes au minimum, 700 au maximum,
ressemblance maximale 80 % avec un autre brouillon (constantes de `warmup.py`). Les autres seuils (plafond 1 sur 10, 1 400 signes, 500 abonnés minimum, 30
jours d'inactivité maximum, 0,3 fil par jour minimum, 65 s entre deux flux) sont des constantes de
`scripts/promo_core/state.py`, `scan.py`, `warmup.py` et `channels/reddit.py`.

## Voir aussi

[Usage](USAGE.md) · [Vie privée et sécurité](PRIVACY_AND_SECURITY.md)
