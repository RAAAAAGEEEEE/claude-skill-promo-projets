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

    def counted(self) -> list[Contribution]:
        return [r for r in self.rows if r.status in COUNTED]

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

    def ratio(self) -> tuple[int, int]:
        """(contributions avec lien, contributions comptées)."""
        counted = self.counted()
        return sum(1 for r in counted if r.has_link), len(counted)


def link_allowed(ledger: Ledger, policy: str, warmup: int = WARMUP_DEFAULT) -> tuple[bool, str]:
    """Le prochain contenu de ce compte peut-il porter un lien ? Retourne (oui/non, raison)."""
    if policy != "declaree-ok":
        return False, {
            "interdit": "règle de la communauté : autopromotion interdite",
            "fil-dedie": "autopromotion limitée à un fil dédié : à traiter à la main, hors repérage",
            "non-verifie": "[NV] règle non lue ou non conclusive",
        }.get(policy, "politique de communauté inconnue")
    counted = ledger.counted()
    no_link = sum(1 for r in counted if not r.has_link)
    if no_link < warmup:
        return False, f"historique à construire : {no_link}/{warmup} contributions sans lien"
    recent = counted[-(LINK_WINDOW - 1):]
    if any(r.has_link for r in recent):
        return False, f"un lien déjà dans les {LINK_WINDOW - 1} dernières contributions (plafond 1 sur {LINK_WINDOW})"
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
