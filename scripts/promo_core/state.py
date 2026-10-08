"""État local : registre des règles lues par communauté et ledger commun des contributions.

Tout vit dans le dossier de données de l'utilisateur (PROMO_DATA_DIR, par défaut ~/.promo-projets),
jamais dans le dépôt du skill.
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, asdict, fields
from datetime import date, datetime, timezone
from pathlib import Path

LINK_WINDOW = 10          # au plus 1 contribution sur 10 contient un lien, tous projets confondus
WARMUP_DEFAULT = 30       # contributions sans lien avant le premier lien (compte crédible d'abord)
COUNTED = ("proposed", "published")  # une proposition compte tant qu'elle n'est pas écartée : plafond plus strict que la pratique
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
POLICIES = ("interdit", "declaree-ok", "fil-dedie", "non-verifie")


def data_dir() -> Path:
    return Path(os.environ.get("PROMO_DATA_DIR") or Path.home() / ".promo-projets")


@dataclass
class Contribution:
    id: str
    date: str
    project: str
    sub: str
    thread_url: str
    kind: str          # comment | post
    has_link: bool
    status: str        # proposed | published | skipped
    note: str = ""
    account: str = ""  # pseudo du compte (registre comptes.json) ; vide = ancien ledger mono-compte
    origin: str = ""   # promo | warmup | manual


COLUMNS = [f.name for f in fields(Contribution)]


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self.rows: list[Contribution] = []
        if path.exists():
            with path.open(newline="", encoding="utf-8") as handle:
                for raw in csv.DictReader(handle):
                    self.rows.append(Contribution(**{**raw, "has_link": raw["has_link"] == "true"}))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            for row in self.rows:
                writer.writerow({**asdict(row), "has_link": "true" if row.has_link else "false"})

    def counted(self, account: str | None = None) -> list[Contribution]:
        """Contributions comptées. `account` restreint au compte donné (le ratio se tient PAR compte)."""
        return [r for r in self.rows if r.status in COUNTED and (account is None or r.account == account)]

    def next_id(self) -> str:
        return f"c{len(self.rows) + 1:04d}"

    def add(self, **kwargs: object) -> Contribution:
        row = Contribution(id=self.next_id(), date=str(kwargs.pop("date", date.today().isoformat())), **kwargs)  # type: ignore[arg-type]
        self.rows.append(row)
        return row

    def find(self, ident: str) -> Contribution:
        for row in self.rows:
            if row.id == ident:
                return row
        raise KeyError(f"contribution inconnue : {ident}")

    def thread_owner(self, thread_url: str) -> str | None:
        for row in self.rows:
            if row.thread_url == thread_url and row.status != "skipped":
                return row.project
        return None

    def known_threads(self) -> set[str]:
        return {r.thread_url for r in self.rows}

    def last_contribution_date(self, project: str) -> str:
        dates = [r.date for r in self.counted() if r.project == project]
        return max(dates) if dates else ""

    def conflict(self, account: str, sub: str, thread_url: str, day: str) -> str | None:
        """Règle dure multi-comptes : jamais deux comptes dans le même fil, ni dans la même communauté le même jour."""
        for r in self.rows:
            if r.status == "skipped" or not r.account or r.account == account:
                continue
            if thread_url and r.thread_url == thread_url:
                return f"le compte {r.account} est déjà dans ce fil"
            if r.sub.lower() == sub.lower() and r.date == day:
                return f"le compte {r.account} est déjà dans r/{sub} aujourd'hui"
        return None

    def ratio(self, account: str | None = None) -> tuple[int, int]:
        """(contributions avec lien, contributions comptées), pour un compte ou tous."""
        counted = self.counted(account)
        return sum(1 for r in counted if r.has_link), len(counted)


def link_allowed(
    ledger: Ledger, policy: str, warmup: int = WARMUP_DEFAULT, account: str | None = None,
    flags: dict | None = None, today: str | None = None,
) -> tuple[bool, str]:
    """Le prochain contenu de ce compte peut-il porter un lien ? Retourne (oui/non, raison).

    `account` : le plafond et l'historique se lisent sur CE compte seulement. `flags` : drapeaux tirés des règles lues.
    """
    if policy != "declaree-ok":
        return False, {
            "interdit": "règle de la communauté : autopromotion interdite",
            "fil-dedie": "autopromotion limitée à un fil dédié : à traiter à la main, hors repérage",
            "non-verifie": "[NV] règle non lue ou non conclusive",
        }.get(policy, "politique de communauté inconnue")
    flags = flags or {}
    if flags.get("autopromo_interdite"):
        return False, "règles lues : autopromotion interdite"
    if flags.get("liens_interdits"):
        return False, "règles lues : liens interdits"
    if flags.get("fil_dedie") and flags.get("jour_autopromo") is None:
        return False, "règles lues : autopromotion limitée à un fil dédié, à traiter à la main"
    day = flags.get("jour_autopromo")
    if day is not None and today and date.fromisoformat(today).weekday() != day:
        return False, f"règles lues : autopromotion seulement le {JOURS[day]}"
    window = max(LINK_WINDOW, int(flags.get("ratio_fenetre") or 0))
    counted = ledger.counted(account)
    no_link = sum(1 for r in counted if not r.has_link)
    if no_link < warmup:
        return False, f"historique à construire : {no_link}/{warmup} contributions sans lien"
    recent = counted[-(window - 1):]
    if any(r.has_link for r in recent):
        return False, f"un lien déjà dans les {window - 1} dernières contributions (plafond 1 sur {window})"
    return True, "plafond respecté et historique suffisant"


class Rules:
    """Registre des communautés : règle lue, politique, citation, date de lecture."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, dict[str, object]] = {}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def record(self, sub: str, policy: str, quote: str, project: str | None = None) -> None:
        if policy not in POLICIES or policy == "non-verifie":
            raise ValueError(f"politique à choisir parmi {', '.join(p for p in POLICIES if p != 'non-verifie')}")
        if not quote.strip():
            raise ValueError("la citation de la règle est obligatoire : sans elle, la règle n'est pas lue")
        self.data[sub.lower()] = {
            "sub": sub,
            "policy": policy,
            "quote": quote.strip(),
            "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "project": project,
        }

    def policy(self, sub: str) -> str:
        return str(self.data.get(sub.lower(), {}).get("policy", "non-verifie"))

    def is_read(self, sub: str) -> bool:
        return sub.lower() in self.data

    def entry(self, sub: str) -> dict:
        return self.data.get(sub.lower(), {})

    def flags(self, sub: str) -> dict:
        """Drapeaux exploitables tirés du texte des règles importé (vide si aucun texte lu)."""
        value = self.entry(sub).get("flags")
        return value if isinstance(value, dict) else {}

    def record_text(self, sub: str, text: str, source: str, flags: dict, derived_policy: str, project: str | None = None) -> str:
        """Enregistre le texte des règles lu (daté) et ses drapeaux. Retourne la politique retenue.

        Une politique posée à la main (avec citation) n'est jamais assouplie par un import : seul un durcissement l'écrase.
        """
        old = self.entry(sub)
        policy = derived_policy
        old_policy = str(old.get("policy", "non-verifie"))
        strict = {"interdit": 3, "fil-dedie": 2, "non-verifie": 1, "declaree-ok": 0}
        if old and strict.get(old_policy, 1) > strict.get(derived_policy, 1):
            policy = old_policy
        elif old and derived_policy == "non-verifie" and old_policy != "non-verifie":
            policy = old_policy
        self.data[sub.lower()] = {
            **old, "sub": sub, "policy": policy, "quote": old.get("quote") or "(texte des règles importé, voir rules_text)",
            "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "project": old.get("project") or project, "rules_text": text.strip()[:20000], "rules_source": source, "flags": flags,
        }
        return policy
