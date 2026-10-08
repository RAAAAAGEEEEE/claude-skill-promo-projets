"""Registre des comptes Reddit de l'utilisateur et règles dures multi-comptes.

Stocké dans comptes.json (dossier de données de l'utilisateur, jamais dans le dépôt). L'outil ne crée aucun compte et ne
se connecte à aucun : ce registre ne décrit que des comptes que l'humain possède déjà.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

HANDLE_RE = re.compile(r"^[A-Za-z0-9_-]{3,20}$")


class AccountError(ValueError):
    pass


def clean_handle(raw: str) -> str:
    handle = raw.strip().removeprefix("/").removeprefix("u/").removeprefix("@")
    if not HANDLE_RE.match(handle):
        raise AccountError(f"pseudo invalide : {raw!r} (3 à 20 lettres, chiffres, tiret, tiret bas)")
    return handle


@dataclass
class Account:
    handle: str
    role: str = ""
    projects: list[str] = field(default_factory=list)
    subs: list[str] = field(default_factory=list)
    karma: int = 0
    since: str = ""          # date de création du compte (AAAA-MM-JJ), pour calculer l'âge
    bans: list[str] = field(default_factory=list)  # communautés où ce compte est banni

    def age_days(self, today: str) -> int:
        if not self.since:
            return 0
        return max(0, (date.fromisoformat(today) - date.fromisoformat(self.since)).days)


class Registry:
    def __init__(self, path: Path):
        self.path = path
        self.accounts: dict[str, Account] = {}
        if path.exists():
            for handle, raw in json.loads(path.read_text(encoding="utf-8")).items():
                self.accounts[handle] = Account(handle=handle, **raw)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {h: {k: v for k, v in a.__dict__.items() if k != "handle"} for h, a in sorted(self.accounts.items())}
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def __bool__(self) -> bool:
        return bool(self.accounts)

    def get(self, handle: str) -> Account:
        key = clean_handle(handle)
        if key not in self.accounts:
            raise KeyError(f"compte inconnu : {key}")
        return self.accounts[key]

    def handles(self) -> set[str]:
        return {h.lower() for h in self.accounts}

    def upsert(self, handle: str, *, role: str | None = None, karma: int | None = None, since: str | None = None) -> Account:
        key = clean_handle(handle)
        account = self.accounts.get(key) or Account(handle=key)
        if role is not None:
            account.role = role
        if karma is not None:
            if karma < 0:
                raise AccountError("karma négatif")
            account.karma = karma
        if since is not None:
            try:
                date.fromisoformat(since)
            except ValueError as error:
                raise AccountError(f"date invalide : {since!r} (AAAA-MM-JJ)") from error
            account.since = since
        self.accounts[key] = account
        return account

    def assign(self, handle: str, projects: list[str], subs: list[str], known_projects: set[str] | None = None) -> Account:
        account = self.get(handle)
        if known_projects is not None:
            unknown = [p for p in projects if p not in known_projects]
            if unknown:
                raise AccountError(f"projet inconnu : {unknown[0]}")
        for p in projects:
            if p not in account.projects:
                account.projects.append(p)
        for s in (x.removeprefix("r/") for x in subs):
            if s.lower() in (b.lower() for b in self.banned_everywhere()):
                raise AccountError(f"r/{s} est fermée : un compte y a été banni, aucun autre compte n'y va (pas de contournement)")
            if s.lower() not in (x.lower() for x in account.subs):
                account.subs.append(s)
        return account

    def ban(self, handle: str, sub: str) -> None:
        """Note un bannissement. La communauté est alors fermée à TOUS les comptes : aucun compte ne sert à contourner un ban."""
        account = self.get(handle)
        sub = sub.removeprefix("r/")
        if sub.lower() not in (b.lower() for b in account.bans):
            account.bans.append(sub)
        for other in self.accounts.values():
            other.subs = [s for s in other.subs if s.lower() != sub.lower()]

    def banned_everywhere(self) -> set[str]:
        return {b.lower() for a in self.accounts.values() for b in a.bans}

    def eligible(self, account: Account, sub: str, flags: dict, today: str, project: str | None = None) -> str | None:
        """None si le compte peut contribuer dans cette communauté aujourd'hui, sinon la raison du refus."""
        if sub.lower() in self.banned_everywhere():
            return f"r/{sub} fermée (bannissement enregistré)"
        if account.subs and sub.lower() not in (s.lower() for s in account.subs):
            return f"r/{sub} non affectée à {account.handle}"
        if project is not None and account.projects and project not in account.projects:
            return f"projet {project} non affecté à {account.handle}"
        need_karma = int(flags.get("karma_min") or 0)
        if account.karma < need_karma:
            return f"karma {account.karma} < {need_karma} exigé par r/{sub}"
        need_age = int(flags.get("age_min_jours") or 0)
        if account.age_days(today) < need_age:
            return f"compte de {account.age_days(today)} j < {need_age} j exigés par r/{sub}"
        return None
