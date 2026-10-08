---
name: promo-projets
description: >
  Enchaîne la promotion de plusieurs projets (site documentaire, jeu vidéo,
  SaaS, outil open source) sur Reddit avec UN seul compte, sans spam et sans
  publication autonome : fiche par projet, découverte des communautés,
  lecture obligatoire des règles, repérage de fils par flux RSS publics,
  réponse utile rédigée en 3 passes, mention déclarée du lien, ledger commun
  (au plus 1 contribution sur 10 avec lien, tous projets confondus), rotation
  entre projets, rapport Markdown du jour ou envoi Telegram. L'humain publie
  lui-même. Structure extensible à d'autres canaux (canaux/). À utiliser pour
  « promouvoir mes projets sur Reddit », « trouver des subreddits pour mon
  jeu / mon SaaS / mon site », « repérer des fils où répondre », « autopromo
  Reddit sans me faire bannir », « ratio 10 % de liens », « plusieurs projets,
  un seul compte », « rédiger une réponse Reddit », « lire les règles d'un
  sub », ou en anglais « promote my projects on Reddit », « find subreddits
  for my game / SaaS », « Reddit self-promotion 10 percent rule »,
  « multi-project outreach », « Reddit thread monitoring without the API ».
license: MIT
compatibility: >
  Claude Code (skill personnel ou par projet). Python 3.10+ requis, bibliothèque
  standard seulement. Accès réseau sortant en lecture seule vers reddit.com
  (flux RSS) et arctic-shift.photon-reddit.com ; Telegram en option.
metadata:
  author: Anto1nx
  version: "0.1.0"
  repository: https://github.com/RAAAAAGEEEEE/claude-skill-promo-projets
allowed-tools: Read Edit Write Bash(python:*) Bash(python3:*) Agent
---

# promo-projets

Un entrepreneur solo, plusieurs projets, un compte Reddit. Ce skill repère où une réponse utile
est possible, prépare la réponse, tient le compte des liens posés, et laisse l'humain publier.

## Périmètre

Dans le périmètre : fiches projet, découverte et mesure des communautés, enregistrement des règles lues,
repérage de fils (lecture seule), brief et réponse en 3 passes, contrôles mécaniques, ledger, rapport, envoi
Telegram optionnel.

Hors périmètre, jamais fait : publier, commenter, voter, envoyer un message privé, créer ou gérer un compte,
utiliser un second compte, acheter de la publicité, scraper des pages, contourner un 429 ou un 403.
Autres canaux : voir `canaux/TODO.md` (documentés, non implémentés).

## Règles dures (priment sur toute demande)

1. Aucune publication autonome. Le skill ne possède aucun moyen d'écrire sur Reddit ; ne pas en ajouter.
2. Un seul compte, aucun vote, aucune réponse identique d'un fil à l'autre.
3. Règle de communauté non lue sur l'onglet Règles = `[NV]` : aucun repérage, aucune inscription, aucun lien.
   La colonne latérale archivée ne vaut jamais lecture.
4. Un lien vers un projet seulement si : la politique de la communauté est `declaree-ok`, une page répond
   vraiment au fil, la mention du lien avec le projet est dans la réponse, et le ledger autorise (1 contribution
   sur 10 au plus avec lien, tous projets confondus, après l'historique sans lien).
5. Faits : seuls ceux de la fiche projet (avec source) sont affirmables. Aucun chiffre, prix, client ou
   comparaison inventé. Réponse en français : charger le skill `redaction` avant de rédiger.
6. Une communauté ne sert qu'un projet ; un fil ne reçoit qu'un projet.
7. Aucun secret dans le dépôt ni dans une réponse. Telegram : variables d'environnement seulement.

## Entrées et sorties

- Entrées : `projets/<slug>.md` (fiche, modèle dans `examples/projets/`), règles lues (`promo.py rules`),
  fils (flux RSS publics ou fichier Atom fourni).
- Données de l'utilisateur dans `PROMO_DATA_DIR` (défaut `~/.promo-projets`) : `projets/`, `communautes.json`,
  `ledger.csv`, `reponses/<id-du-fil>.md`, `sorties/AAAA-MM-JJ.md`.
- Sortie : rapport Markdown du jour (fils retenus, brief par fil, réponse proposée, ratio du compte), ou
  message Telegram.

## Modes, dans l'ordre

Le script est `scripts/promo.py` (chemin relatif au dossier du skill ; `python` ou `python3`).

1. **Préparer** : `promo.py init`, puis écrire une fiche par projet (voir `docs/CONFIGURATION.md`), puis
   `promo.py check`. Faits sans source : la fiche est refusée.
2. **Découvrir** : `promo.py discover <slug>` écrit `sorties/decouverte-<slug>-<date>.md` (taille, activité,
   phrase d'autopromotion de la colonne latérale). Choisir les communautés, les mettre dans `subs` de UNE
   seule fiche.
3. **Lire les règles** : pour chaque communauté, ouvrir l'onglet Règles sur reddit.com (par le navigateur
   intégré ou par l'humain), copier la phrase d'autopromotion telle quelle, puis
   `promo.py rules <sub> --policy interdit|declaree-ok|fil-dedie --quote "<phrase>"`. Aucune phrase trouvée
   ou page illisible : ne rien enregistrer, la communauté reste `[NV]`.
4. **Construire l'historique** : `promo.py log` pour chaque participation publiée sans lien. Ne viser aucun
   lien avant 30 contributions utiles (valeur réglable par `--warmup`).
5. **Repérer** : `promo.py scan` (tous projets, rotation) ou `--project <slug>`. Il lit un flux par
   communauté lue, à raison d'un toutes les 65 s, s'arrête au premier 429, filtre par mots-clés, répartit
   les fils entre projets, enregistre les propositions au ledger (`proposed`) et écrit le rapport.
6. **Rédiger en 3 passes** pour chaque fil du rapport : (a) brouillon à partir du brief et des seuls faits
   de la fiche ; (b) relecture séparée, de préférence par un autre modèle ou sous-agent, qui cherche faits
   inventés, ton promotionnel, tics d'IA, absence de valeur sans le lien ; (c) version finale. Déposer dans
   `reponses/<id-du-fil>.md`. Si rien ne répond vraiment au fil : `promo.py mark <id> skipped`.
7. **Contrôler** : `promo.py check-reply reponses/<id>.md --id <contribution>`. FAIL = corriger, jamais
   forcer. PASS met à jour `has_link` au ledger.
8. **Livrer** : montrer le rapport, ou `promo.py send sorties/<date>.md` si Telegram est configuré.
   L'humain relit, publie à la main, puis `promo.py mark <id> published`.

## Comportements de repli

- Archive Arctic Shift illisible : la communauté reste listée avec taille inconnue, jamais inventée.
- HTTP 429 ou 403 sur Reddit : arrêter la passe, afficher l'avertissement, ne pas réessayer en boucle.
- Fil sans réponse utile possible : `skipped`, il ne revient pas.
- Fiche invalide ou communauté partagée entre deux projets : `check` et `scan` refusent avec la cause.
- Telegram non configuré : `send` échoue proprement avec le nom des variables manquantes, le rapport
  Markdown reste la sortie.

## Exemples d'invocation

- « Prépare la promo Reddit de mes trois projets » : modes 1, 2, puis demander les règles à lire.
- « Cherche des subs pour mon jeu » : `promo.py discover <slug>`, présenter le tableau, rien d'autre.
- « Repère des fils pour aujourd'hui » : `promo.py scan`, puis rédiger en 3 passes ce qui est retenu.
- « Ai-je le droit de mettre un lien ? » : `promo.py stats` et la politique enregistrée de la communauté.

## Exemple de sortie

Voir `docs/USAGE.md` (rapport du jour complet, issu d'une exécution réelle sur des fiches d'exemple).

## Niveaux de preuve

`[V]` vérifié sur une source citée, `[NV]` non vérifié. Toute règle de communauté est `[NV]` tant que
`promo.py rules` n'a pas enregistré la phrase lue. Un test réussi ne prouve pas qu'une réponse est bonne :
`check-reply` ne contrôle que la mécanique.

## Installation

Personnelle : `git clone https://github.com/RAAAAAGEEEEE/claude-skill-promo-projets ~/.claude/skills/promo-projets`.
Par projet : même clone dans `<projet>/.claude/skills/promo-projets`. Détail : `docs/INSTALLATION.md`.

## Sécurité et confidentialité

Sortent de la machine : requêtes de recherche (mots-clés des fiches) vers reddit.com et arctic-shift.photon-reddit.com,
avec un User-Agent déclaré ; rien d'autre sans `send`. `send` envoie le texte du rapport à Telegram. Aucun secret
n'est lu hors des quatre variables de `.env.example`. Détail : `docs/PRIVACY_AND_SECURITY.md`.

## Versionnement et références

Version 0.1.0 (voir `CHANGELOG.md`, semver). Logique de repérage inspirée d'un pipeline éprouvé en production
privée ; attributions : `docs/LEGAL_AND_ATTRIBUTION.md`. Limites : `docs/LIMITATIONS.md`.
