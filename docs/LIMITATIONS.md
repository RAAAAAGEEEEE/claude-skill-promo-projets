# Limites

- **Règles de communauté : lecture réseau fragile.** `rules fetch` tente rules.json puis old.reddit.com ; depuis
  certains PC, Reddit répond par une page de vérification (constaté le 08/10/2026 : 403 sur rules.json, page de
  vérification sur old.reddit.com). Il faut alors lire l'onglet Règles dans un navigateur et `rules import`. Les
  drapeaux sont des heuristiques sur du texte libre (anglais et français) : ils peuvent rater une formulation ; le texte
  intégral reste stocké pour relecture, et le silence sur l'autopromotion ne vaut jamais autorisation. La colonne
  latérale archivée par Arctic Shift peut dater de plusieurs mois.
- **Karma et âge saisis à la main.** Le registre ne se connecte à aucun compte : il ne sait pas qu'un compte a été
  suspendu, ni que son karma a changé.
- **Chauffe : choix mécanique des fils, rédaction externe.** `warmup` choisit les fils par motifs (question, avis,
  remerciement) et contrôle les brouillons mécaniquement (longueur, générique, lien, doublon, mots en commun avec le
  fil) ; il ne juge pas que le contenu est vrai ni vraiment utile, et n'écrit rien lui-même sans `--drafter` ou Claude.
- **Page du jour : pas de lecture de ce qui est publié.** « Marquer publié » repose sur la bonne foi de l'utilisateur ;
  le ledger ne vérifie pas que le commentaire existe.
- **Détection d'un fil écrit par un de tes comptes** : seulement si le flux indique l'auteur.
- **Repérage dépendant de flux non garantis.** Les flux RSS publics de Reddit peuvent répondre 429 ou 403 sans
  préavis ; la passe s'arrête et affiche l'avertissement. Un jour de repérage peut ne rien rendre.
- **Archive à délai.** Arctic Shift peut avoir quelques jours de retard ; la taille et la cadence affichées
  sont indicatives.
- **Mots-clés, pas compréhension.** Le score filtre les fils ; il ne juge ni la qualité d'un fil ni l'ironie.
  La décision « une page répond vraiment » reste humaine.
- **Contrôles mécaniques seulement.** `check-reply` ne vérifie pas qu'un fait est vrai ni qu'une réponse est
  utile. Le tiret cadratin est refusé par choix de style, pas par règle de Reddit.
- **Reddit seul.** Les autres canaux sont documentés dans [canaux/TODO.md](../canaux/TODO.md) sans code.
- **Fenêtre de 30 contributions** avant le premier lien : valeur de prudence de ce skill, sans source
  officielle. Le plafond d'une contribution sur dix reprend la consigne générale de Reddit citée dans
  [LEGAL_AND_ATTRIBUTION.md](LEGAL_AND_ATTRIBUTION.md), elle aussi sans seuil officiel chiffré vérifié.
- **Pas de mesure de résultats.** Aucune statistique de clics ou de votes n'est lue.
- **Testé** sur Python 3.11 (Windows 11). Python 3.10 non exécuté.
- **Pas de garantie contre un bannissement** : deux comptes qui promeuvent les mêmes projets restent liés aux yeux de
  Reddit ; le skill réduit le risque, il ne le supprime pas.

## Voir aussi

[Dépannage](TROUBLESHOOTING.md) · [Vie privée et sécurité](PRIVACY_AND_SECURITY.md)
