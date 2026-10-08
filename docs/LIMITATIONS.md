# Limites

- **Règles de communauté non lues automatiquement.** Aucune source gratuite ne livre le texte à jour de
  l'onglet Règles : l'API officielle est soumise à approbation et les pages sont bloquées pour les scripts.
  La lecture est donc humaine (ou faite par un navigateur piloté par l'utilisateur) et enregistrée par `rules`.
  La colonne latérale archivée par Arctic Shift peut dater de plusieurs mois.
- **Repérage dépendant de flux non garantis.** Les flux RSS publics de Reddit peuvent répondre 429 ou 403 sans
  préavis ; la passe s'arrête et affiche l'avertissement. Un jour de repérage peut ne rien rendre.
- **Archive à délai.** Arctic Shift peut avoir quelques jours de retard ; la taille et la cadence affichées
  sont indicatives.
- **Mots-clés, pas compréhension.** Le score filtre les fils ; il ne juge ni la qualité d'un fil ni l'ironie.
  La décision « une page répond vraiment » reste humaine.
- **Contrôles mécaniques seulement.** `check-reply` ne vérifie pas qu'un fait est vrai ni qu'une réponse est
  utile. Le tiret cadratin est refusé par choix de style, pas par règle de Reddit.
- **Un compte, Reddit seul.** Pas de gestion de plusieurs comptes (volontaire) ; les autres canaux sont
  documentés dans [canaux/TODO.md](../canaux/TODO.md) sans code.
- **Fenêtre de 30 contributions** avant le premier lien : valeur de prudence de ce skill, sans source
  officielle. Le plafond d'une contribution sur dix reprend la consigne générale de Reddit citée dans
  [LEGAL_AND_ATTRIBUTION.md](LEGAL_AND_ATTRIBUTION.md), elle aussi sans seuil officiel chiffré vérifié.
- **Pas de mesure de résultats.** Aucune statistique de clics ou de votes n'est lue.
- **Testé** sur Python 3.11 (Windows 11). Python 3.10 non exécuté.

## Voir aussi

[Dépannage](TROUBLESHOOTING.md) · [Vie privée et sécurité](PRIVACY_AND_SECURITY.md)
