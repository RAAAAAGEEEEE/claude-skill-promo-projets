"""Fiches projet : lecture, validation, garde-fous multi-projets."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .miniyaml import MiniYamlError, parse_front_matter

SUB_RE = re.compile(r"^[A-Za-z0-9_]{2,21}$")
URL_RE = re.compile(r"^https?://\S+$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


class ProjectError(ValueError):
    pass


@dataclass(frozen=True)
class Keyword:
    keyword: str
    weight: int = 1
    mode: str = "word"  # word | prefix | regex


@dataclass(frozen=True)
class Fact:
    text: str
    source: str


@dataclass
class Project:
    slug: str
    nom: str
    type: str
    pitch: str
    public: str
    liens: list[str]
    faits: list[Fact]
    mots_cles: list[Keyword]
    mots_exclus: list[str]
    langues: list[str]
    subs: list[str]
    mention: list[str]
    requetes_communautes: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def main_link(self) -> str:
        return self.liens[0]


def _parse_keyword(raw: str) -> Keyword:
    parts = [p.strip() for p in raw.split("|")]
    word = parts[0]
    weight = int(parts[1]) if len(parts) > 1 and parts[1] else 1
    mode = parts[2] if len(parts) > 2 and parts[2] else "word"
    if not word or weight < 1 or mode not in ("word", "prefix", "regex"):
        raise ProjectError(f"mot-clé invalide : {raw!r} (forme : mot | poids | word|prefix|regex)")
    return Keyword(word, weight, mode)


def _parse_fact(raw: str) -> Fact:
    text, _, source = raw.rpartition("|")
    text, source = text.strip(), source.strip()
    if not text or not URL_RE.match(source):
        raise ProjectError(f"fait sans source : {raw!r} (forme : fait | https://source). Un fait non sourcé n'est pas affirmable.")
    return Fact(text, source)


def _as_list(value: object, name: str) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ProjectError(f"{name} doit être une liste")
    return [str(v) for v in value]


def load_project(path: Path) -> Project:
    slug = path.stem
    if not SLUG_RE.match(slug):
        raise ProjectError(f"{path.name} : le nom du fichier doit être un slug (a-z, 0-9, tirets)")
    try:
        data, body = parse_front_matter(path.read_text(encoding="utf-8"))
    except MiniYamlError as error:
        raise ProjectError(f"{path.name} : {error}") from error
    for required in ("nom", "pitch", "public", "liens", "mots_cles", "langues", "subs", "mention"):
        if data.get(required) in (None, "", []):
            raise ProjectError(f"{path.name} : champ obligatoire vide ou absent : {required}")
    liens = _as_list(data["liens"], "liens")
    bad = [u for u in liens if not URL_RE.match(u)]
    if bad:
        raise ProjectError(f"{path.name} : lien invalide : {bad[0]}")
    subs = [s.removeprefix("r/") for s in _as_list(data["subs"], "subs")]
    bad_subs = [s for s in subs if not SUB_RE.match(s)]
    if bad_subs:
        raise ProjectError(f"{path.name} : nom de communauté invalide : {bad_subs[0]}")
    langues = _as_list(data["langues"], "langues")
    return Project(
        slug=slug,
        nom=str(data["nom"]),
        type=str(data.get("type", "autre")),
        pitch=str(data["pitch"]),
        public=str(data["public"]),
        liens=liens,
        faits=[_parse_fact(f) for f in _as_list(data.get("faits"), "faits")],
        mots_cles=[_parse_keyword(k) for k in _as_list(data["mots_cles"], "mots_cles")],
        mots_exclus=_as_list(data.get("mots_exclus"), "mots_exclus"),
        langues=langues,
        subs=subs,
        mention=_as_list(data["mention"], "mention"),
        requetes_communautes=_as_list(data.get("requetes_communautes"), "requetes_communautes"),
        notes=body,
    )


def load_projects(directory: Path) -> dict[str, Project]:
    if not directory.is_dir():
        raise ProjectError(f"dossier de fiches introuvable : {directory}")
    projects: dict[str, Project] = {}
    for path in sorted(directory.glob("*.md")):
        if path.name.startswith("_"):
            continue
        projects[path.stem] = load_project(path)
    return projects


def validate_portfolio(projects: dict[str, Project]) -> list[str]:
    """Erreurs bloquantes entre projets : une communauté ne sert qu'un seul projet."""
    errors: list[str] = []
    owner: dict[str, str] = {}
    for slug, project in projects.items():
        for sub in project.subs:
            key = sub.lower()
            if key in owner and owner[key] != slug:
                errors.append(f"communauté r/{sub} revendiquée par {owner[key]} et {slug} : une communauté ne sert qu'un projet")
            owner[key] = slug
    return errors
