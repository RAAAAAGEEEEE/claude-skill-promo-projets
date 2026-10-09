---
name: promo-projets
description: >
  Forge de promotion Reddit semi-automatique pour plusieurs projets (site documentaire, jeu vidéo, SaaS, outil open
  source) et un ou plusieurs comptes que tu possèdes déjà : registre des comptes (karma, âge, affectation aux projets et
  communautés), chauffe quotidienne par compte (brouillons utiles sans lien), lecture et import des règles de
  communauté (drapeaux : autopromo interdite, ratio, karma ou âge minimum, jour dédié, liens interdits), repérage de
  fils par flux RSS publics, réponse de promo en 3 passes avec mention déclarée du lien, ledger commun (au plus 1
  contribution sur 10 avec lien, PAR COMPTE), page HTML du jour avec boutons Copier / Ouvrir le fil / Marquer publié,
  tâche `daily` planifiable. L'humain publie toujours lui-même (dernier clic). Structure extensible à d'autres canaux
  (canaux/). À utiliser pour « promouvoir mes projets sur Reddit », « chauffer mes comptes Reddit », « deux comptes
  Reddit, plusieurs projets », « trouver des subreddits pour mon jeu / mon SaaS / mon site », « repérer des fils où
  répondre », « autopromo Reddit sans me faire bannir », « ratio 10 % de liens », « lire les règles d'un sub »,
  « page du jour de promo », ou en anglais « promote my projects on Reddit », « Reddit account warm-up »,
  « Reddit self-promotion 10 percent rule », « multi-account outreach », « Reddit thread monitoring without the API ».
license: MIT
compatibility: >
  Claude Code (skill personnel ou par projet). Python 3.10+ requis, bibliothèque standard seulement. Accès réseau
  sortant en lecture seule vers reddit.com et old.reddit.com (flux RSS, règles) et arctic-shift.photon-reddit.com ;
  Telegram en option ; serveur local optionnel sur 127.0.0.1.
metadata:
  author: Anto1nx
  version: "0.2.0"
  repository: https://github.com/RAAAAAGEEEEE/claude-skill-promo-projets
allowed-tools: Read Edit Write Bash(python:*) Bash(python3:*) Agent
---

# promo-projets

Un entrepreneur solo, plusieurs projets, un ou plusieurs comptes Reddit. Ce skill repère où une réponse utile est
possible, prépare les brouillons (chauffe et promo), tient le compte des liens posés par compte, et laisse l'humain
publier : le dernier clic lui appartient toujours.

## Périmètre

Dans le périmètre : fiches projet, registre des comptes que l'utilisateur possède déjà, découverte et mesure des
communautés, lecture et import des règles, repérage de fils (lecture seule), chauffe, brief et réponse en 3 passes,
contrôles mécaniques, ledger, page HTML du jour, serveur local facultatif, rapport, envoi Telegram optionnel.

Hors périmètre, jamais fait : publier, commenter, voter, envoyer un message privé, créer un compte, se connecter à un
compte, acheter de la publicité, scraper des pages, contourner un 429, un 403 ou une page de vérification, utiliser un
compte pour contourner un bannissement.
Autres canaux : voir `canaux/TODO.md` (documentés, non implémentés).

## Règles dures (priment sur toute demande)

1. Aucune publication autonome. Le skill ne possède aucun moyen d'écrire sur Reddit ; ne pas en ajouter. Le bouton
   « Marquer publié » ne fait qu'inscrire au ledger ce que l'humain a déjà publié.
2. Multi-comptes (codé, testé) : jamais deux comptes dans le même fil ni dans la même communauté le même jour ; jamais
   de vote ni de réponse d'un compte à un fil écrit par un autre de tes comptes (ni de renvoi vers lui dans un brouillon) ;
   aucun compte créé ni utilisé pour contourner un bannissement (`accounts ban` ferme la communauté à TOUS les comptes) ;
   le ratio de liens (au plus 1 contribution sur 10, ou la fenêtre imposée par la communauté si elle est plus large) se
   tient PAR COMPTE.
3. Règle de communauté non lue = `[NV]` : aucun repérage, aucune chauffe, aucun lien. Lire = enregistrer la phrase
   (`rules --quote`) ou le texte des règles (`rules fetch` / `rules import`). La colonne latérale archivée ne vaut jamais
   lecture. Un texte qui ne parle pas d'autopromotion donne `non-verifie` : chauffe possible, jamais de lien.
4. Un lien vers un projet seulement si : la politique de la communauté est `declaree-ok` (et les drapeaux lus le
   permettent : ni autopromo interdite, ni liens interdits, bon jour, fenêtre de ratio), une page répond vraiment au
   fil, la mention du lien avec le projet est dans la réponse, et le ledger du COMPTE autorise.
5. Chauffe : brouillons SANS lien ni mention de projet, réellement utiles (au moins 15 mots, portant sur le fil), jamais
   génériques (« great post », emoji seul), jamais copiés d'un fil à l'autre, au plus 2 par communauté, compte et jour.
6. Faits : seuls ceux de la fiche projet (avec source) sont affirmables. Aucun chiffre, prix, client ou comparaison
   inventé. Réponse en français : charger le skill `redaction` avant de rédiger.
6 bis. Ton humain, jamais « IA » : écrire comme un membre du sub, pas comme un assistant. Phrases courtes et
   inégales, registre de la communauté (tutoiement, argot du sub, minuscules tolérées), une seule idée, avis ou
   expérience à la première personne quand c'est vrai. Interdits : formules d'ouverture ou de clôture (« Great
   question! », « Hope this helps », « N'hésite pas »), listes à puces et titres dans un commentaire court, tiret
   cadratin, gras, triplets d'adjectifs, reformulation de la question, ton promotionnel, emoji décoratif. Relecture
   finale : si une phrase pourrait sortir de ChatGPT, la réécrire ou la couper.
7. Une communauté ne sert qu'un projet ; un fil ne reçoit qu'un projet. Chaque compte chauffe dans les communautés de
   TOUS les projets (sauf `accounts assign --subs` qui le restreint) ; ses liens ne visent que ses projets affectés.
   Jamais deux comptes dans le même fil ni dans la même communauté le même jour.
8. Aucun secret ni pseudo réel dans le dépôt ni dans une réponse. Telegram : variables d'environnement seulement.

## Entrées et sorties

- Entrées : `projets/<slug>.md` (fiche, modèle dans `examples/projets/`), `comptes.json`, règles lues, fils (flux RSS
  publics ou fichier Atom fourni).
- Données de l'utilisateur dans `PROMO_DATA_DIR` (défaut `~/.promo-projets`) : `projets/`, `comptes.json`,
  `communautes.json`, `ledger.csv`, `fils.json`, `reponses/<id-du-fil>.md`, `chauffe/<date>/<compte>__<id-du-fil>.md`,
  `sorties/AAAA-MM-JJ.md` et `.html`.
- Sorties : rapport Markdown, page HTML du jour (par compte : texte, communauté, boutons), message Telegram facultatif.

## Modes, dans l'ordre

Le script est `scripts/promo.py` (chemin relatif au dossier du skill ; `python` ou `python3`).

1. **Préparer** : `promo.py init`, une fiche par projet (voir `docs/CONFIGURATION.md`), `promo.py check`.
2. **Comptes** (si plusieurs) : `promo.py accounts add <pseudo> --role principal --karma N --age-days N`, puis
   `promo.py accounts assign <pseudo> --projects slug1,slug2 --subs SubA,SubB`. Un bannissement :
   `promo.py accounts ban <pseudo> <sub>`. Un compte sans affectation ne reçoit rien.
3. **Découvrir** : `promo.py discover <slug>` écrit `sorties/decouverte-<slug>-<date>.md`. Choisir les communautés, les
   mettre dans `subs` d'UNE seule fiche (promo) ou dans `--subs` d'un compte (chauffe seule).
4. **Lire les règles**, dans cet ordre :
   a. `promo.py rules fetch <sub>` essaie `https://www.reddit.com/r/<sub>/about/rules.json` puis
      `https://old.reddit.com/r/<sub>/about/rules/` (User-Agent descriptif). Depuis certains PC, www.reddit.com répond
      par une page HTML de vérification : la commande le détecte, n'enregistre rien et affiche la méthode b.
   b. Méthode navigateur : ouvrir `https://old.reddit.com/r/<sub>/about/rules` dans le navigateur intégré (outils
      `mcp__Claude_Browser__*`, lire d'abord le skill `anthropic-skills:built-in-browser`), `get_page_text`, enregistrer le
      texte dans un fichier (outil Write), puis `promo.py rules import <sub> --from-text <fichier>`.
   c. Le texte est stocké daté avec ses drapeaux (autopromo interdite, ratio imposé, karma min, compte min, jour dédié,
      fil dédié, liens interdits), affichés par la commande. Relire la phrase d'autopromotion : si le texte l'autorise
      sans la citer clairement, `promo.py rules <sub> --policy declaree-ok --quote "<phrase>"` (action humaine ou
      validée). Une politique posée à la main n'est jamais assouplie par un import.
5. **Construire l'historique** : `promo.py log --account <pseudo> ...` ou `promo.py ledger add --id cNNNN` pour chaque
   publication sans lien. Aucun lien avant 30 contributions sans lien du compte (`--warmup`).
6. **Chauffe** : `promo.py warmup run [--per-account 4] [--per-sub 2]` choisit par compte N fils (3 à 5) dans ses
   communautés lues (question, avis demandé, remerciement), les enregistre au ledger (sans lien) et prépare les briefs.
   Rédiger chaque brouillon (2 à 5 phrases utiles, sans lien ni projet) dans
   `chauffe/<date>/<compte>__<id-du-fil>.md`, ou donner `--drafter "<commande>"` qui reçoit le brief JSON sur stdin.
   `promo.py warmup check` : FAIL = corriger, jamais forcer.
7. **Repérer la promo** : `promo.py scan` (ou `--project`). Il lit un flux par communauté lue (un toutes les 65 s, arrêt
   au premier 429), répartit les fils entre projets, affecte un compte éligible (projet, communauté, karma, âge,
   conflits), enregistre les propositions au ledger et écrit le rapport.
8. **Rédiger en 3 passes** chaque réponse de promo : (a) brouillon à partir du brief et des seuls faits de la fiche ;
   (b) relecture séparée, de préférence par un autre modèle ou sous-agent ; (c) version finale dans
   `reponses/<id-du-fil>.md`. Rien ne répond au fil : `promo.py mark <id> skipped`.
9. **Contrôler** : `promo.py check-reply reponses/<id>.md --id <contribution>`. FAIL = corriger.
10. **Livrer** : `promo.py page` écrit `sorties/AAAA-MM-JJ.html` (à ouvrir dans le navigateur) ; ou `promo.py serve`
    (127.0.0.1 seulement) pour que « Marquer publié » enregistre le clic directement. L'humain copie, ouvre le fil,
    publie avec le bon compte, puis marque publié (`promo.py ledger add --id cNNNN` en mode fichier).
11. **Planifier** : `promo.py daily` enchaîne repérage, chauffe, contrôle des réponses de promo déposées, page du jour ;
    idempotent (relancé le même jour : aucun doublon ni nouvel appel réseau ; `--force` pour refaire). Option
    `--telegram` pour un court résumé. À mettre dans une tâche planifiée quotidienne ; Claude rédige ensuite les
    brouillons manquants (modes 6 et 8) puis relance `promo.py page`.

12. **Retours** (projet en test, on cherche des avis plutôt que des clients) : poser dans le post des questions
    précises (ce qui bloque, ce qui est trop dur ou trop facile, ce qu'on attendait) au lieu de « dites-moi ce que
    vous en pensez » ; un seul sujet par question, trois au plus. Répondre à chaque retour par un remerciement court,
    sans défense ni argumentaire, et une question de précision si le retour est flou. Chaque retour utile est
    enregistré (`promo.py feedback add --project <slug> --source <communauté> --kind bug|difficulte|interface|contenu|idee|compliment|autre
    --severity 1|2|3 --text "<paraphrase>"`, sans pseudo), puis `promo.py feedback summary --project <slug>` donne la
    liste par gravité à convertir en éléments de backlog ; `feedback status --index N --status retenu|fait|ecarte`
    suit le sort de chaque retour. Un retour répété par plusieurs personnes pèse plus qu'un avis isolé ; un compliment
    n'est jamais un motif de relancer la communauté. Le sort d'un retour est annoncé aux auteurs seulement par une
    réponse publiée par l'humain, jamais par le skill.

## Comportements de repli

- Règles illisibles par le réseau (page de vérification, 403, 429) : méthode navigateur du mode 4b ; sinon la
  communauté reste `[NV]`.
- Archive Arctic Shift illisible : la communauté reste listée avec taille inconnue, jamais inventée.
- HTTP 429 ou 403 sur Reddit : arrêter la passe, afficher l'avertissement, ne pas réessayer en boucle.
- Fil sans réponse utile possible : `skipped`, il ne revient pas.
- Fiche invalide ou communauté partagée entre deux projets : `check` et `scan` refusent avec la cause.
- Aucun compte enregistré : `scan` et `daily` fonctionnent comme en 0.1 (un compte implicite) ; `warmup` demande un compte.
- Telegram non configuré : `send` échoue proprement avec le nom des variables manquantes, le rapport
  Markdown reste la sortie.

## Exemples d'invocation

- « Prépare la promo Reddit de mes trois projets » : modes 1 à 4, puis demander les règles à lire.
- « Cherche des subs pour mon jeu » : `promo.py discover <slug>`, présenter le tableau, rien d'autre.
- « Chauffe mes deux comptes aujourd'hui » : `promo.py daily`, puis rédiger les brouillons manquants et `promo.py page`.
- « Importe les règles de r/X » : mode 4b (navigateur intégré, get_page_text, `rules import`).
- « Repère des fils pour aujourd'hui » : `promo.py scan`, puis rédiger en 3 passes ce qui est retenu.
- « Ai-je le droit de mettre un lien ? » : `promo.py stats` (par compte) et la politique enregistrée de la communauté.

## Exemple de sortie

Voir `docs/USAGE.md` (rapport du jour, sorties de `rules import` et de `stats` par compte, page du jour, issus
d'exécutions réelles sur des fiches d'exemple).

## Niveaux de preuve

`[V]` vérifié sur une source citée, `[NV]` non vérifié. Toute règle de communauté est `[NV]` tant que `promo.py rules`
n'a pas enregistré une phrase ou un texte lu. Un test réussi ne prouve pas qu'une réponse est bonne : `check-reply` et
`warmup check` ne contrôlent que la mécanique.

## Installation

Personnelle : `git clone https://github.com/RAAAAAGEEEEE/claude-skill-promo-projets ~/.claude/skills/promo-projets`.
Par projet : même clone dans `<projet>/.claude/skills/promo-projets`. Détail : `docs/INSTALLATION.md`.

## Sécurité et confidentialité

Sortent de la machine : requêtes de lecture (mots-clés des fiches, noms de communautés) vers reddit.com, old.reddit.com et
arctic-shift.photon-reddit.com, avec un User-Agent déclaré ; rien d'autre sans `send` ni `daily --telegram`. Le serveur
local n'écoute que 127.0.0.1 (jeton par page, contrôle du Host). `--drafter` lance une commande que tu choisis et lui
envoie le titre et l'extrait d'un fil. Aucun secret n'est lu hors des quatre variables de `.env.example`. Détail :
`docs/PRIVACY_AND_SECURITY.md`.

## Versionnement et références

Version 0.3.0 (voir `CHANGELOG.md`, semver). Logique de repérage inspirée d'un pipeline éprouvé en production
privée ; attributions : `docs/LEGAL_AND_ATTRIBUTION.md`. Limites : `docs/LIMITATIONS.md`.
