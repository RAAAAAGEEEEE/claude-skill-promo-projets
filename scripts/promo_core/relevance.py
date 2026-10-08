"""Score par mots-clés d'un fil avant tout appel à un modèle (mots entiers, accents ignorés)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .project import Keyword
from .textutil import normalize

MIN_THREAD_SCORE = 2


@dataclass(frozen=True)
class Score:
    score: int
    matched: list[str]


def _matches(haystack: str, kw: Keyword) -> bool:
    if kw.mode == "regex":
        try:
            return re.search(kw.keyword, haystack, re.I) is not None
        except re.error:
            return False  # un motif cassé retire ce mot-clé, jamais tout le calcul
    pattern = re.escape(normalize(kw.keyword)).replace(r"\ ", r"\s+")
    before = r"(?<![^\W_])"
    after = r"(?![^\W_])"
    regex = before + pattern + (after if kw.mode == "word" else "")
    return re.search(regex, haystack) is not None


def score_thread(title: str, text: str, keywords: list[Keyword], excluded: list[str] | None = None) -> Score:
    haystack = normalize(f"{title}\n{text}")
    for word in excluded or []:
        if _matches(haystack, Keyword(word, 1, "word")):
            return Score(0, [f"exclu:{word}"])
    matched = [k.keyword for k in keywords if _matches(haystack, k)]
    total = sum(k.weight for k in keywords if k.keyword in matched)
    return Score(total, matched)


def is_relevant(score: Score, minimum: int = MIN_THREAD_SCORE) -> bool:
    return score.score >= minimum
