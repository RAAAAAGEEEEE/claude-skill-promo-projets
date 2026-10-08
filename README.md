# promo-projets

Skill Claude Code pour promouvoir plusieurs projets (site documentaire, jeu vidéo, SaaS, outil) sur Reddit
avec un seul compte, sans spam et sans publication autonome. L'outil repère, prépare et tient les comptes ;
c'est toi qui publies.

## Le problème

Un entrepreneur solo qui a trois projets et un seul compte Reddit se fait bannir de deux façons : en postant
un lien dans chaque réponse, ou en poussant plusieurs projets dans les mêmes communautés. Reddit demande
surtout de la participation réelle et, pour l'autopromotion, une déclaration claire ; les règles varient par
communauté et l'API de données n'est plus en libre-service.

## Pour qui

Fondateurs solo ou petites équipes qui ont au moins deux projets à faire connaître et acceptent de publier
à la main.

## Ce qu'il apporte

- Une fiche par projet : pitch, public, liens, faits sourcés (un fait sans source est refusé), mots-clés.
- Découverte de communautés par flux RSS publics et archive Arctic Shift, avec taille et activité.
- Règle non lue = `[NV]` : pas de repérage, pas de lien tant que la phrase de l'onglet Règles n'est pas enregistrée.
- Repérage de fils par flux RSS publics (pas d'API, pas de jeton), espacé de 65 s, arrêt au premier 429.
- Ledger commun : au plus 1 contribution sur 10 avec lien, tous projets confondus, rotation entre projets,
  jamais deux projets dans un même fil, communautés séparées par projet.
- Brief par fil pour une réponse en 3 passes, contrôles mécaniques (`check-reply`), rapport Markdown du jour
  ou envoi Telegram.

## Statut

Alpha (0.1.0). Reddit seul est implémenté ; les autres canaux sont documentés dans
[canaux/TODO.md](canaux/TODO.md). 51 tests automatiques ; le repérage en conditions réelles dépend de la
disponibilité des flux publics de Reddit (voir [docs/LIMITATIONS.md](docs/LIMITATIONS.md)).

## Prérequis

Python 3.10 ou plus, Git, Claude Code. Aucune dépendance à installer.

## Quickstart

```bash
git clone https://github.com/RAAAAAGEEEEE/claude-skill-promo-projets ~/.claude/skills/promo-projets
cd ~/.claude/skills/promo-projets
python -m unittest discover -s tests
python scripts/promo.py init
python scripts/promo.py check
```

`init` crée `~/.promo-projets/` avec deux fiches fictives. Les remplacer par tes projets, puis suivre
[docs/USAGE.md](docs/USAGE.md).

## Exemple minimal

```bash
python scripts/promo.py rules Lighthouses --policy declaree-ok --quote "Self-promotion is allowed if you disclose your link."
python scripts/promo.py scan --project atlas-des-phares --from-feed fil.xml
```

Sortie : un rapport `~/.promo-projets/sorties/AAAA-MM-JJ.md` (exemple complet dans [docs/USAGE.md](docs/USAGE.md)).
Dans Claude Code, demander par exemple « repère des fils Reddit pour mes projets » : le skill suit la procédure
de [SKILL.md](SKILL.md).

## Architecture

Un script (`scripts/promo.py`) et une bibliothèque (`scripts/promo_core/`) : fiches, règles, ledger, canal
Reddit en lecture seule, planification, contrôles, Telegram. Détail : [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Configuration

Quatre variables d'environnement facultatives, un dossier de données. Détail :
[docs/CONFIGURATION.md](docs/CONFIGURATION.md) et [.env.example](.env.example).

## Sécurité et confidentialité

Lecture seule vers Reddit et Arctic Shift, aucun secret dans le dépôt, Telegram optionnel.
Détail : [docs/PRIVACY_AND_SECURITY.md](docs/PRIVACY_AND_SECURITY.md) et [SECURITY.md](SECURITY.md).

## Limites

Pas de lecture automatique de l'onglet Règles, pas de publication, un compte, Reddit seul, mots-clés
plutôt que compréhension. Liste complète : [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Roadmap non contractuelle

Autres canaux (voir [canaux/TODO.md](canaux/TODO.md)), lecture des règles via l'API officielle si l'accès
est un jour accordé, import de fils depuis des alertes e-mail.

## Documentation

[Installation](docs/INSTALLATION.md) · [Usage](docs/USAGE.md) · [Configuration](docs/CONFIGURATION.md) ·
[Architecture](docs/ARCHITECTURE.md) · [Dépannage](docs/TROUBLESHOOTING.md) · [Limites](docs/LIMITATIONS.md) ·
[Vie privée et sécurité](docs/PRIVACY_AND_SECURITY.md) · [Mentions légales et attributions](docs/LEGAL_AND_ATTRIBUTION.md) ·
[Changelog](CHANGELOG.md) · [Contribuer](CONTRIBUTING.md)

## Licence

MIT, voir [LICENSE](LICENSE).
