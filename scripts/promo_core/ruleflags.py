"""Texte des règles d'une communauté -> drapeaux exploitables par le planificateur.

Heuristiques en anglais et en français. Elles ne remplacent pas la lecture : le texte intégral reste stocké, daté, à côté
des drapeaux. Dans le doute, un drapeau restrictif est posé (mieux vaut renoncer à un lien que se faire retirer).
"""
from __future__ import annotations

import re

from .textutil import normalize, sentences

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6,
}
_PROMO = re.compile(r"self ?promo\w*|autopromo\w*|auto promo\w*|advertis\w*|publicit\w*|promot\w*|showcase|show ?off|spam\w*|shameless plug", re.I)
_FORBID = re.compile(
    r"\b(no|not allowed|not permitted|do not|don t|dont|never|prohibited|banned|forbidden|without|interdit\w*|pas de|aucune?|ne pas)\b"
    r"|\b(is|are) (strictly )?(not|never) (allowed|permitted|tolerated|accepted)\b",
    re.I,
)
_ALLOWED_ONLY = re.compile(r"\b(except|unless|only|sauf|uniquement|seulement|exclusively)\b", re.I)
_DEDICATED = re.compile(r"\b(mega ?thread|dedicated thread|weekly thread|monthly thread|pinned thread|stickied|fil dedie|fil hebdomadaire|fil mensuel)\b", re.I)
_NO_LINKS = re.compile(
    r"\b(no|not|never|without|interdit\w*|pas de|aucun)\b[^.\n]{0,40}\b(external |outside )?(links?|urls?|liens?)\b"
    r"|\b(links?|urls?|liens?)\b[^.\n]{0,40}\b(not allowed|prohibited|banned|forbidden|removed|interdit\w*)\b",
    re.I,
)
_LINK_OK_CONTEXT = re.compile(r"\b(only|except|unless|sauf|uniquement|seulement)\b", re.I)
_RATIO = [
    re.compile(r"\b(\d{1,2})\s*[:/]\s*1\b"),
    re.compile(r"\b1\s*(?:out of|in|of|sur)\s*(?:every\s*|each\s*)?(\d{1,3})\b", re.I),
    re.compile(r"\b(\d{1,2})\s*%"),
]
_KARMA = re.compile(r"(\d{1,6})\+?\s*(?:combined |total |comment |post |link )?karma|karma (?:of |de |minimum |min )?(?:at least |minimum |of )?(\d{1,6})", re.I)
_AGE = [
    re.compile(r"(\d{1,3}) ?(day|week|month|year|jour|semaine|mois|an)s? old", re.I),
    re.compile(r"(?:account|compte)[^.\n]{0,40}?(\d{1,3}) ?(day|week|month|year|jour|semaine|mois|an)s?", re.I),
]
_UNIT_DAYS = {"day": 1, "jour": 1, "week": 7, "semaine": 7, "month": 30, "mois": 30, "year": 365, "an": 365}


def parse_flags(text: str) -> dict:
    """Retourne les drapeaux. Booleens toujours presents ; les autres seulement si detectes."""
    flags: dict = {"autopromo_interdite": False, "liens_interdits": False, "fil_dedie": False}
    for sentence in sentences(text):
        norm = normalize(sentence)
        has_promo = bool(_PROMO.search(norm))
        day = next((d for name, d in _WEEKDAYS.items() if re.search(rf"\b{name}s?\b", norm)), None)
        if has_promo and day is not None and "jour_autopromo" not in flags:
            flags["jour_autopromo"] = day
        if has_promo and _DEDICATED.search(norm):
            flags["fil_dedie"] = True
        if has_promo and _FORBID.search(norm):
            conditional = bool(_ALLOWED_ONLY.search(norm)) and (day is not None or bool(_DEDICATED.search(norm)))
            if not conditional:
                flags["autopromo_interdite"] = True
        if _NO_LINKS.search(norm) and not _LINK_OK_CONTEXT.search(norm):
            flags["liens_interdits"] = True
        if has_promo or "ratio" in norm or "rule" in norm or "regle" in norm:
            for pattern in _RATIO:
                m = pattern.search(norm)
                if not m:
                    continue
                n = int(m.group(1))
                if pattern is _RATIO[2]:
                    window = round(100 / n) if 0 < n <= 50 else 0
                elif pattern is _RATIO[0]:
                    window = n + 1
                else:
                    window = n
                if 2 <= window <= 100:
                    flags["ratio_fenetre"] = max(window, flags.get("ratio_fenetre", 0))
                break
        for m in _KARMA.finditer(norm):
            value = int(m.group(1) or m.group(2))
            if value > 0:
                flags["karma_min"] = max(value, flags.get("karma_min", 0))
        for pattern in _AGE:
            m = pattern.search(norm)
            if m:
                flags["age_min_jours"] = max(int(m.group(1)) * _UNIT_DAYS[m.group(2).lower()], flags.get("age_min_jours", 0))
                break
    if flags.get("jour_autopromo") is not None:
        flags["autopromo_interdite"] = False  # l'interdiction est conditionnee au jour dedie
    return flags


def derive_policy(flags: dict) -> str:
    """Politique deduite du texte. `declaree-ok` seulement si le texte encadre explicitement l'autopromotion (ratio, jour)."""
    if flags.get("autopromo_interdite") or flags.get("liens_interdits"):
        return "interdit"
    if flags.get("jour_autopromo") is not None or flags.get("ratio_fenetre"):
        return "declaree-ok"
    if flags.get("fil_dedie"):
        return "fil-dedie"
    return "non-verifie"  # silence sur l'autopromotion : ce n'est pas une autorisation


def describe(flags: dict) -> str:
    from .state import JOURS

    parts = []
    if flags.get("autopromo_interdite"):
        parts.append("autopromo interdite")
    if flags.get("liens_interdits"):
        parts.append("liens interdits")
    if flags.get("fil_dedie"):
        parts.append("fil dédié")
    if flags.get("jour_autopromo") is not None:
        parts.append(f"autopromo le {JOURS[flags['jour_autopromo']]}")
    if flags.get("ratio_fenetre"):
        parts.append(f"ratio imposé 1 sur {flags['ratio_fenetre']}")
    if flags.get("karma_min"):
        parts.append(f"karma min {flags['karma_min']}")
    if flags.get("age_min_jours"):
        parts.append(f"compte min {flags['age_min_jours']} j")
    return ", ".join(parts) or "aucun drapeau détecté"
