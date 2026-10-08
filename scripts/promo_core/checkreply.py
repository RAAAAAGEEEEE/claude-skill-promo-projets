"""Contrôles mécaniques d'une réponse avant publication. Ils n'ont jamais valeur de relecture éditoriale."""
from __future__ import annotations

import difflib
import re

from .project import Project
from .scan import MAX_REPLY_CHARS

_URL = re.compile(r"https?://[^\s)>\]]+", re.I)
_DASHES = re.compile("[–—]|--")


def _norm_url(url: str) -> str:
    return url.rstrip(".,;:!?").lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")


def project_links_in(text: str, project: Project) -> list[str]:
    bases = [_norm_url(u) for u in project.liens]
    return [u for u in _URL.findall(text) if any(_norm_url(u).startswith(b) for b in bases)]


def check_reply(
    text: str,
    project: Project,
    link_permitted: bool,
    thread_text: str = "",
    others: dict[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    """Retourne (erreurs bloquantes, avertissements)."""
    errors: list[str] = []
    warnings: list[str] = []
    body = text.strip()
    if not body:
        return ["réponse vide"], warnings
    if len(body) > MAX_REPLY_CHARS:
        errors.append(f"trop longue : {len(body)} signes (maximum {MAX_REPLY_CHARS})")
    if _DASHES.search(body):
        errors.append("tiret cadratin, demi-cadratin ou double trait d'union (signature de texte généré)")
    urls = _URL.findall(body)
    own = project_links_in(body, project)
    foreign = [u for u in urls if u not in own]
    if foreign:
        errors.append(f"adresse absente de la fiche projet : {foreign[0]}")
    mention = any(m.lower() in body.lower() for m in project.mention)
    if own and not link_permitted:
        errors.append("lien vers le projet alors que le plafond ou la règle de la communauté ne l'autorise pas")
    if own and not mention:
        errors.append("lien vers le projet sans la mention de ton lien avec lui (une des phrases de `mention` de la fiche)")
    if mention and not own:
        warnings.append("mention du lien avec le projet sans lien : acceptable, mais vérifier que c'est voulu")
    allowed_numbers = set(re.findall(r"\d+", " ".join([project.pitch, project.public, thread_text] + [f.text for f in project.faits])))
    unknown = sorted(set(re.findall(r"\d+", body)) - allowed_numbers)
    if unknown:
        warnings.append("chiffre(s) absent(s) de la fiche et du fil, à sourcer ou retirer : " + ", ".join(unknown[:6]))
    for name, other in (others or {}).items():
        if difflib.SequenceMatcher(None, body, other.strip()).ratio() > 0.8:
            errors.append(f"quasi identique à une autre réponse ({name}) : jamais de réponse copiée d'un fil à l'autre")
    return errors, warnings
