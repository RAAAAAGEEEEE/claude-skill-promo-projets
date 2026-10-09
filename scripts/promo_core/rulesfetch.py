"""Lecture des règles d'une communauté : rules.json, old.reddit.com, puis la copie datée de l'archive Arctic Shift,
avec détection propre d'une page de vérification."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Callable

from .channels.reddit import ARCHIVE, Fetcher, http_get
from .textutil import strip_tags

MIN_TEXT = 40
ARCHIVE_STALE_DAYS = 90  # au-delà, la copie de l'archive est signalée comme ancienne
_BLOCK_MARKERS = (
    "verification", "verify you are", "captcha", "blocked by network security", "network security",
    "enable javascript", "unusual traffic", "access denied", "just a moment", "cloudflare",
)
_SCRIPTS = re.compile(r"<(script|style|noscript)\b.*?</\1>", re.S | re.I)


def looks_like_html(body: str) -> bool:
    head = body.lstrip()[:200].lower()
    return head.startswith("<!doctype") or head.startswith("<html") or "<html" in head


def is_block_page(body: str) -> bool:
    low = body.lower()
    return looks_like_html(body) and any(m in low for m in _BLOCK_MARKERS) and len(strip_tags(_SCRIPTS.sub(" ", body))) < 1500


def rules_from_json(body: str) -> str | None:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    rules = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(rules, list) or not rules:
        return None
    lines = []
    for index, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            continue
        name = str(rule.get("short_name") or rule.get("violation_reason") or "").strip()
        desc = str(rule.get("description") or "").strip()
        lines.append(f"{index}. {name}\n{desc}".strip())
    return "\n\n".join(lines) or None


def rules_from_archive(body: str, now: float | None = None) -> tuple[str | None, str, list[str]]:
    """Règles de la réponse Arctic Shift (/subreddits/rules) : (texte, source datée, avertissements)."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None, "", ["archive Arctic Shift : réponse illisible"]
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        return None, "", ["archive Arctic Shift : aucune règle connue pour cette communauté"]
    text = rules_from_json(json.dumps({"rules": items[0].get("rules")}))
    if not text:
        return None, "", ["archive Arctic Shift : aucune règle connue pour cette communauté"]
    retrieved = items[0].get("retrieved_on")
    if not isinstance(retrieved, (int, float)):
        return text, "arctic-shift (date inconnue)", ["archive Arctic Shift : date de la copie inconnue, à confirmer sur Reddit avant tout lien"]
    day = datetime.fromtimestamp(retrieved, timezone.utc).strftime("%Y-%m-%d")
    age = ((now if now is not None else time.time()) - retrieved) / 86400
    warnings = []
    if age > ARCHIVE_STALE_DAYS:
        warnings.append(f"archive Arctic Shift : copie du {day} ({int(age)} jours), à confirmer sur Reddit avant tout lien")
    return text, f"arctic-shift (copie du {day})", warnings


def text_from_old_reddit(body: str) -> str:
    return strip_tags(_SCRIPTS.sub(" ", body))


def fetch_rules(sub: str, fetch: Fetcher = http_get, sleep: Callable[[float], None] = time.sleep) -> tuple[str | None, str, list[str]]:
    """Retourne (texte ou None, source, avertissements). Ordre : www rules.json, old.reddit.com about/rules, puis la
    copie datée de l'archive Arctic Shift (Reddit bloque souvent les deux premières hors navigateur)."""
    warnings: list[str] = []
    status, body = fetch(f"https://www.reddit.com/r/{sub}/about/rules.json")
    if status == 200:
        text = rules_from_json(body)
        if text:
            return text, "rules.json", warnings
        if looks_like_html(body):
            warnings.append("www.reddit.com a renvoyé une page HTML de vérification au lieu du JSON des règles")
        else:
            warnings.append("rules.json illisible (JSON sans règles)")
    elif status == 429:
        return None, "", ["HTTP 429 sur rules.json : arrêt, ne pas réessayer en boucle"]
    elif looks_like_html(body):
        warnings.append(f"www.reddit.com a renvoyé une page HTML de vérification (statut {status}) au lieu du JSON des règles")
    else:
        warnings.append(f"rules.json refusé (statut {status})")
    sleep(3)
    status, body = fetch(f"https://old.reddit.com/r/{sub}/about/rules/")
    if status == 200 and not is_block_page(body):
        text = text_from_old_reddit(body)
        if len(text) >= MIN_TEXT:
            return text, "old.reddit.com", warnings
        warnings.append("old.reddit.com : page sans texte de règles (rendue par JavaScript)")
    elif status == 429:
        warnings.append("HTTP 429 sur old.reddit.com : arrêt")
    elif is_block_page(body):
        warnings.append(f"old.reddit.com a renvoyé une page de vérification (statut {status})")
    else:
        warnings.append(f"old.reddit.com refusé (statut {status})")
    sleep(3)
    status, body = fetch(f"{ARCHIVE}/subreddits/rules?subreddits={urllib.parse.quote(sub)}")
    if status == 200:
        text, source, more = rules_from_archive(body)
        warnings.extend(more)
        if text:
            return text, source, warnings
    else:
        warnings.append(f"archive Arctic Shift refusée (statut {status})")
    return None, "", warnings
