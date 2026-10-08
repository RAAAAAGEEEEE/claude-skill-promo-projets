"""Envoi optionnel d'un rapport vers Telegram. Variables d'environnement seulement, jamais de valeur dans le dépôt."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable

CHUNK = 3800


class TelegramConfigError(RuntimeError):
    pass


def chunks(text: str, size: int = CHUNK) -> list[str]:
    parts: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > size and current:
            parts.append(current)
            current = ""
        while len(line) > size:
            parts.append(line[:size])
            line = line[size:]
        current += line
    if current.strip():
        parts.append(current)
    return parts


def _post(url: str, payload: dict) -> int:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status


def send(text: str, dry_run: bool = False, post: Callable[[str, dict], int] = _post) -> int:
    """Envoie le texte en messages successifs. Retourne le nombre de messages (ou à envoyer en dry_run)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        raise TelegramConfigError("TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID doivent être définies dans l'environnement")
    parts = chunks(text)
    if dry_run:
        return len(parts)
    for part in parts:
        post(f"https://api.telegram.org/bot{token}/sendMessage", {"chat_id": chat, "text": part, "disable_web_page_preview": True})
    return len(parts)
