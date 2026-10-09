# promo-projets

Skill Claude Code : une « forge » de promotion Reddit semi-automatique pour plusieurs projets (site documentaire,
jeu vidéo, SaaS, outil) et un ou plusieurs comptes que tu possèdes déjà. Elle repère, prépare les brouillons, tient
les comptes et prépare une page du jour ; c'est toi qui publies, toujours (le dernier clic).

## Le problème

Un entrepreneur solo qui a plusieurs projets se fait bannir de trois façons : un lien dans chaque réponse, plusieurs
projets dans les mêmes communautés, ou des comptes qui se répondent. Reddit demande de la participation réelle et, pour
l'autopromotion, une déclaration claire ; les règles varient par communauté et l'API de données n'est plus en
libre-service.

## Pour qui

Fondateurs solo ou petites équipes qui ont au moins deux projets à faire connaître, un ou deux comptes Reddit déjà
actifs, et qui acceptent de publier à la main.

## Ce qu'il apporte

- Fiche par projet : pitch, public, liens, faits sourcés (un fait sans source est refusé), mots-clés.
- **Multi-comptes** : registre (pseudo, rôle, projets et communautés affectés, karma, âge). Règles dures codées : jamais
  deux comptes dans le même fil ni la même communauté le même jour, jamais de réponse d'un compte à l'autre, un
  bannissement ferme la communauté à tous les comptes, ratio de liens (au plus 1 sur 10) tenu PAR COMPTE.
- **Chauffe** : chaque jour, par compte, 3 à 5 fils où une réponse courte et utile est possible, brouillons SANS lien ni
  mention de projet ; réponses génériques, emoji seul, copier-coller et excès par communauté refusés.
- **Règles lues** : `rules fetch` (rules.json, old.reddit.com, puis copie datée de l'archive Arctic Shift ; détection d'une
  page de vérification) ou
  `rules import` depuis un texte lu dans le navigateur ; drapeaux (autopromo interdite, ratio, karma ou âge minimum, jour
  dédié, liens interdits) respectés par le planificateur.
- **Page du jour** : un fichier HTML sans dépendance, par compte : texte, communauté, boutons Copier, Ouvrir le fil,
  Marquer publié. Serveur local facultatif (`serve`, 127.0.0.1) qui enregistre le clic.
- **`daily`** : repérage, chauffe, contrôle des réponses de promo, page du jour ; idempotent, pour une tâche planifiée.
- Découverte de communautés, repérage par flux RSS publics (65 s entre deux, arrêt au premier 429), rotation entre
  projets, rapport Markdown, Telegram facultatif.

## Statut

Alpha (0.2.0). Reddit seul est implémenté ; les autres canaux sont documentés dans [canaux/TODO.md](canaux/TODO.md).
Suite de tests automatiques, réseau simulé (`python -m unittest discover -s tests`). Le repérage en conditions réelles
dépend de la disponibilité des flux publics de Reddit (voir [docs/LIMITATIONS.md](docs/LIMITATIONS.md)).

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

## Exemple minimal (deux comptes)

```bash
python scripts/promo.py accounts add compte_a --role principal --karma 400 --age-days 700
python scripts/promo.py accounts assign compte_a --projects atlas-des-phares --subs Lighthouses
python scripts/promo.py rules import Lighthouses --from-text regles-lighthouses.txt
python scripts/promo.py daily
```

Sortie : `~/.promo-projets/sorties/AAAA-MM-JJ.html` (page du jour) et `.md` (rapport). Exemple complet, sorties réelles
comprises : [docs/USAGE.md](docs/USAGE.md). Dans Claude Code, demander par exemple « chauffe mes comptes Reddit
aujourd'hui » : le skill suit la procédure de [SKILL.md](SKILL.md).

## Architecture

Un script (`scripts/promo.py`) et une bibliothèque (`scripts/promo_core/`) : fiches, comptes, règles et drapeaux,
ledger, canal Reddit en lecture seule, planification, chauffe, page du jour, contrôles, Telegram. Détail :
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Configuration

Quatre variables d'environnement facultatives, un dossier de données. Détail :
[docs/CONFIGURATION.md](docs/CONFIGURATION.md) et [.env.example](.env.example).

## Sécurité et confidentialité

Lecture seule vers Reddit et Arctic Shift, aucun secret dans le dépôt, aucun compte créé ni connecté, serveur local
limité à 127.0.0.1, Telegram optionnel. Détail : [docs/PRIVACY_AND_SECURITY.md](docs/PRIVACY_AND_SECURITY.md) et
[SECURITY.md](SECURITY.md).

## Limites

Lecture réseau des règles fragile (page de vérification possible), drapeaux par heuristiques, karma et âge saisis à la
main, choix des fils de chauffe mécanique, aucune garantie contre un bannissement, Reddit seul. Liste complète :
[docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Roadmap non contractuelle

Autres canaux (voir [canaux/TODO.md](canaux/TODO.md)), lecture des règles via l'API officielle si l'accès est un jour
accordé, import de fils depuis des alertes e-mail.

## Documentation

[Installation](docs/INSTALLATION.md) · [Usage](docs/USAGE.md) · [Configuration](docs/CONFIGURATION.md) ·
[Architecture](docs/ARCHITECTURE.md) · [Dépannage](docs/TROUBLESHOOTING.md) · [Limites](docs/LIMITATIONS.md) ·
[Vie privée et sécurité](docs/PRIVACY_AND_SECURITY.md) · [Mentions légales et attributions](docs/LEGAL_AND_ATTRIBUTION.md) ·
[Changelog](CHANGELOG.md) · [Contribuer](CONTRIBUTING.md)

## Licence

MIT, voir [LICENSE](LICENSE).
