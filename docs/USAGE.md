# Utilisation

Toutes les commandes se lancent depuis le dossier du skill. Sous Windows, `python` ; ailleurs `python3` si
`python` n'existe pas. Options globales (avant la commande) : `--data-dir`, `--date AAAA-MM-JJ`, `--warmup N`.

## Parcours complet

1. Initialiser : `python scripts/promo.py init`.
2. Écrire une fiche par projet dans `~/.promo-projets/projets/<slug>.md` (format :
   [CONFIGURATION.md](CONFIGURATION.md)), puis `python scripts/promo.py check`.
3. Découvrir : `python scripts/promo.py discover <slug>`. Une requête toutes les 65 s, donc environ dix
   minutes pour huit requêtes. Le rapport `sorties/decouverte-<slug>-<date>.md` liste taille, activité et la
   phrase d'autopromotion de la colonne latérale (souvent ancienne). Mettre les communautés choisies dans
   `subs` d'une seule fiche.
4. Lire les règles de chaque communauté : `python scripts/promo.py rules fetch <sub>` ou, si le réseau est bloqué,
   `rules import` (voir la section « Forge multi-comptes »). Sinon, lire l'onglet Règles sur reddit.com puis enregistrer :
   `python scripts/promo.py rules Lighthouses --policy declaree-ok --quote "phrase copiée telle quelle"`.
   Politiques : `interdit` (aucun lien), `declaree-ok` (lien permis si déclaré), `fil-dedie` (lien seulement
   dans un fil prévu, traité à la main). Pas de phrase d'autopromotion trouvée : ne rien enregistrer.
5. Construire l'historique : après chaque participation sans lien publiée,
   `python scripts/promo.py log --project <slug> --sub <sub> --url <adresse du commentaire>`.
6. Repérer : `python scripts/promo.py scan` (tous projets) ou `--project <slug>`. `--dry-run` n'écrit pas
   au ledger. `--from-feed fichier.xml` lit un flux Atom déjà enregistré au lieu du réseau.
7. Rédiger chaque réponse en 3 passes (procédure de [SKILL.md](../SKILL.md)), l'enregistrer dans
   `reponses/<id-du-fil>.md`, puis `python scripts/promo.py check-reply reponses/<id>.md --id c0001`.
8. Publier à la main, puis `python scripts/promo.py mark c0001 published`. Fil sans intérêt :
   `python scripts/promo.py mark c0001 skipped`.
9. Suivre : `python scripts/promo.py stats` (global et par compte).
10. Telegram (facultatif) : `python scripts/promo.py send sorties/AAAA-MM-JJ.md`, avec `--dry-run` pour compter
    les messages sans envoyer.

## Forge multi-comptes (0.2.0)

Quand tu as plusieurs comptes, la chauffe et la page du jour s'ajoutent au parcours ci-dessus.

1. Comptes : `accounts add <pseudo> --role principal --karma N --age-days N`, puis
   `accounts assign <pseudo> --projects slug --subs SubA,SubB` ; `accounts list` affiche le registre ;
   `accounts ban <pseudo> <sub>` ferme une communauté à tous les comptes.
2. Règles de chaque communauté : `rules fetch <sub>`. Si Reddit répond par une page de vérification (cas de certains PC),
   la commande n'enregistre rien et indique la méthode : ouvrir `https://old.reddit.com/r/<sub>/about/rules` dans le
   navigateur intégré de Claude, lire la page (`get_page_text`), enregistrer le texte dans un fichier, puis
   `rules import <sub> --from-text <fichier>`. La sortie liste les drapeaux détectés et la politique retenue.
3. Chauffe : `warmup run --per-account 4 --per-sub 2`, rédiger les brouillons dans
   `chauffe/AAAA-MM-JJ/<compte>__<id-du-fil>.md` (ou `--drafter "<commande>"`), `warmup check`.
4. Page du jour : `page` écrit `sorties/AAAA-MM-JJ.html`. Ouvrir ce fichier : par compte, le texte, la communauté, les
   boutons Copier, Ouvrir le fil et Marquer publié. Après avoir publié toi-même avec le bon compte, « Marquer publié »
   affiche la commande `promo.py ledger add --id cNNNN` à coller dans le terminal. Variante : `serve` (127.0.0.1, port
   8765 par défaut) ouvre la même page et enregistre le clic directement.
5. Tout d'un coup, pour une tâche planifiée quotidienne : `daily` (options : `--per-account`, `--per-sub`, `--max`,
   `--no-scan`, `--no-warmup`, `--force`, `--telegram`, `--drafter`). Relancé le même jour, il ne duplique rien.

Exécution réelle (08/10/2026, fiches d'exemple, pseudos fictifs, flux Reddit simulés, `--warmup 0` pour la démonstration) :

```text
$ promo.py rules import Lighthouses --from-text regles.txt
r/Lighthouses : règles enregistrées (import (navigateur), 158 signes, datées). Drapeaux : ratio imposé 1 sur 10, karma min 50.
politique retenue : declaree-ok
$ promo.py daily --per-account 2
1/4 repérage
1 fil(s) retenu(s), rapport : <données>/sorties/2026-10-08.md
2/4 chauffe
chauffe : 4 nouveau(x) fil(s), 4 au total aujourd'hui, 0 brouillon(s) valide(s)
3/4 réponses de promo
4/4 page du jour
page du jour : <données>/sorties/2026-10-08.html
$ promo.py daily --per-account 2
1/4 repérage : déjà fait aujourd'hui
2/4 chauffe (déjà faite, brouillons revérifiés)
chauffe : 0 nouveau(x) fil(s), 4 au total aujourd'hui, 0 brouillon(s) valide(s)
...
$ promo.py stats
- compte compte_a (principal, karma 400, 700 j) : 0 lien sur 3, prochain lien possible (plafond respecté et historique suffisant)
- compte compte_b (second, karma 120, 200 j) : 0 lien sur 2, prochain lien possible (plafond respecté et historique suffisant)
```

« 0 brouillon(s) valide(s) » : aucun brouillon n'était encore rédigé ; la page affiche « Brouillon à rédiger » pour chacun.

Contrôles de la chauffe (`warmup check`) : brouillon vide ou emoji seul, réponse générique (« great post »), moins de 15
mots ou 90 signes, plus de 700 signes, lien ou adresse, nom de projet ou phrase de mention, tiret cadratin, mention d'un de
tes autres comptes, aucun mot en commun avec le fil, ressemblance de plus de 80 % avec un autre brouillon ou une
réponse de promo, plus de `--per-sub` brouillons dans une communauté pour un compte le même jour.

## Règles appliquées par le code

- Un lien n'est permis que si la communauté est `declaree-ok`, que les règles lues ne l'interdisent pas (autopromo,
  liens, jour dédié), que `--warmup` contributions sans lien sont comptées pour CE compte (30 par défaut, choix de
  prudence propre à ce skill, pas une règle de Reddit), qu'aucun lien ne figure dans les 9 dernières contributions
  comptées de ce compte (tous projets ; fenêtre plus large si la communauté impose un ratio plus strict), et qu'aucun
  autre lien n'est déjà autorisé dans la même passe pour ce compte.
- Jamais deux comptes dans le même fil ni dans la même communauté le même jour (`log`, `scan` et `warmup` le refusent) ;
  jamais de fil écrit par un de tes comptes ; un compte sous le karma ou l'âge exigés par une communauté n'y reçoit rien.
- Les propositions comptent dans le ratio dès `scan` (statut `proposed`), publiées ou non : le plafond est donc
  plus strict que la pratique. `skipped` ne compte pas.
- `check-reply` refuse : réponse vide ou de plus de 1 400 signes, tiret cadratin, demi-cadratin ou `--`,
  adresse absente de la fiche, lien non permis, lien sans mention du lien avec le projet, réponse quasi
  identique (plus de 80 % de ressemblance) à une autre du dossier `reponses/`. Il avertit sur les chiffres absents
  de la fiche et du fil.

## Exemple de sortie

Exécution réelle (08/10/2026) sur la fiche d'exemple `atlas-des-phares`, avec un flux Atom fabriqué pour
l'exemple et `--warmup 0` pour la démonstration :

```text
# Promotion du 2026-10-08

Ratio global du compte : 0 contribution(s) avec lien sur 1 comptée(s) (plafond : 1 sur 10, tous projets).
Rien n'est publié par l'outil : tu relis, tu copies, tu publies toi-même sous ton compte.

## 1. Atlas des Phares : r/Lighthouses

- Fil : https://www.reddit.com/r/Lighthouses/comments/abc123/quel_phare/
- Titre : Quel phare visiter en Bretagne cet ete ?
- Score mots-clés : 3 (phare, Fresnel)
- Identifiant ledger : c0001
- Lien vers le projet : AUTORISÉ si une page répond vraiment au fil (plafond respecté et historique suffisant)

> Je cherche un phare ouvert au public, avec une lentille de Fresnel visible.

### Brief de rédaction

- Pitch : Base documentaire gratuite sur les phares de France, une fiche par phare.
- Faits affirmables (seuls autorisés) :
  - Chaque fiche indique la date de mise en service du phare (source : https://example.org/atlas-des-phares/methode)
- Lien à utiliser : https://example.org/atlas-des-phares
- Mention obligatoire avec le lien (une de) : Je tiens Atlas des Phares / Full disclosure, I run Atlas des Phares
- Longueur maximale : 1400 signes

### Réponse proposée

À rédiger en 3 passes (brouillon, relecture séparée, version finale) puis à déposer dans `reponses/abc123.md`.
```

(Extrait : le rapport réel contient aussi le public, les langues et tous les faits.)

## Voir aussi

[Configuration](CONFIGURATION.md) · [Dépannage](TROUBLESHOOTING.md) · [Limites](LIMITATIONS.md)
