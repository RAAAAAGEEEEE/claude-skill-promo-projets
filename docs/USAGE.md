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
4. Lire l'onglet Règles de chaque communauté sur reddit.com, puis enregistrer :
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
9. Suivre : `python scripts/promo.py stats`.
10. Telegram (facultatif) : `python scripts/promo.py send sorties/AAAA-MM-JJ.md`, avec `--dry-run` pour compter
    les messages sans envoyer.

## Règles appliquées par le code

- Un lien n'est permis que si la communauté est `declaree-ok`, que `--warmup` contributions sans lien sont
  comptées (30 par défaut, choix de prudence propre à ce skill, pas une règle de Reddit), qu'aucun lien ne figure
  dans les 9 dernières contributions comptées (tous projets), et qu'aucun autre lien n'est déjà autorisé dans la
  même passe.
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
