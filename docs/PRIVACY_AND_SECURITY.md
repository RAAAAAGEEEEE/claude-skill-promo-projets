# Vie privée et sécurité

## Ce qui sort de la machine

| Destination | Quoi | Quand |
|---|---|---|
| `www.reddit.com` (flux RSS, GET) | requête de recherche : mots-clés de la fiche, nom d'une communauté, User-Agent déclaré | `discover`, `scan` |
| `www.reddit.com` et `old.reddit.com` (GET) | nom d'une communauté (règles, derniers fils), User-Agent déclaré | `rules fetch`, `warmup`, `daily` |
| `arctic-shift.photon-reddit.com` (GET) | nom d'une communauté | `discover` |
| `api.telegram.org` (POST) | texte du rapport envoyé | seulement sur `send` sans `--dry-run`, ou `daily --telegram` |

Rien d'autre. Aucun cookie, aucun compte Reddit, aucun jeton Reddit : l'outil ne s'authentifie nulle part auprès
de Reddit et ne peut donc rien y écrire.

## Secrets

Seuls `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` sont secrets. Ils se lisent dans l'environnement, jamais dans
un fichier du dépôt, et ne sont ni affichés ni journalisés. Une erreur d'envoi n'affiche que le type de
l'exception, pas son message (qui pourrait citer l'adresse contenant le jeton).

## Données personnelles

Les fiches, le ledger et les réponses vivent dans `PROMO_DATA_DIR`, hors du dépôt. Le ledger contient des
adresses de tes propres commentaires et des noms de communautés ; il ne stocke aucun pseudo d'autres
utilisateurs. Les extraits de fils du rapport viennent de contenus publics et ne sont pas conservés ailleurs
que dans le rapport.

## Garde-fous contre l'abus

Aucune création de compte, aucune connexion à un compte, pas de vote, pas de publication ; jamais deux comptes dans le
même fil ou la même communauté le même jour, jamais de réponse d'un compte à l'autre, bannissement = communauté fermée
à tous les comptes ; ratio de liens par compte ; chauffe sans lien ni mention de projet ; délais de 65 s respectés, arrêt au premier 429, aucun
contournement de blocage. Ne pas ajouter ces fonctions : voir [CONTRIBUTING.md](../CONTRIBUTING.md).

## Serveur local et rédacteur externe

`promo.py serve` écoute sur 127.0.0.1 uniquement, refuse tout `Host` qui n'est pas local (anti-rebond DNS) et exige un
jeton aléatoire, propre à chaque page servie, pour enregistrer un clic (anti-CSRF). Il n'écrit que dans `ledger.csv`.
La page est un fichier sans script externe ni appel réseau ; le texte venu de Reddit y est échappé, et seuls les liens
de fils Reddit https sont rendus cliquables. `--drafter` exécute la commande que tu fournis (sans shell) et lui envoie le
titre et l'extrait du fil ; ne pas y mettre de commande non fiable.

## Signaler une faille

Voir [SECURITY.md](../SECURITY.md).

## Voir aussi

[Configuration](CONFIGURATION.md) · [Mentions légales et attributions](LEGAL_AND_ATTRIBUTION.md)
