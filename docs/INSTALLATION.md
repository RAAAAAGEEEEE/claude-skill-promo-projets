# Installation

Prérequis : Python 3.10 ou plus (`python --version`), Git, Claude Code. Aucun paquet à installer.

## Personnelle (tous tes projets)

```bash
git clone https://github.com/RAAAAAGEEEEE/claude-skill-promo-projets ~/.claude/skills/promo-projets
cd ~/.claude/skills/promo-projets
python -m unittest discover -s tests
python scripts/promo.py init
```

Sous Windows, `~` désigne `C:\Users\<toi>` dans Git Bash et PowerShell (`$HOME`). Relancer Claude Code pour que
le skill soit listé.

## Par projet

Même clone dans `<projet>/.claude/skills/promo-projets`. Le dossier de données reste personnel
(`~/.promo-projets`) : les fiches de tes projets ne doivent pas entrer dans un dépôt partagé.

## Vérification

Les tests finissent par `OK` (51 tests). `python scripts/promo.py check` affiche le nombre de projets et le
ratio du ledger.

## Mise à jour

`git -C ~/.claude/skills/promo-projets pull`, puis relancer les tests. Lire [CHANGELOG.md](../CHANGELOG.md) avant.

## Voir aussi

[Usage](USAGE.md) · [Dépannage](TROUBLESHOOTING.md)
