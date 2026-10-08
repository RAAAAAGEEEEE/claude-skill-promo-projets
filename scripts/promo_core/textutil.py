"""Utilitaires texte : normalisation, décodage HTML, découpe de phrases."""
from __future__ import annotations

import html
import re
import unicodedata

_TAGS = re.compile(r"<[^>]+>")
_COMMENTS = re.compile(r"<!--.*?-->", re.S)


def normalize(text: str) -> str:
    """Minuscules, accents retirés, apostrophes et traits d'union lus comme des espaces."""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = stripped.lower()
    lowered = re.sub(r"[’'‑-]", " ", lowered)
    return re.sub(r"\s+", " ", lowered)


def strip_tags(markup: str) -> str:
    text = _COMMENTS.sub(" ", markup)
    text = _TAGS.sub(" ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def sentences(text: str) -> list[str]:
    cleaned = re.sub(r"[*_>#`]", " ", text)
    cleaned = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cleaned)
    parts = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    return [re.sub(r"\s+", " ", p).strip() for p in parts if p.strip()]
