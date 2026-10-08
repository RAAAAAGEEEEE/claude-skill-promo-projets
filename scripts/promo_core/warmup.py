"""Chauffe (warm-up) : proposer chaque jour, par compte, des fils où une réponse courte mais réellement utile est possible.

Brouillons SANS lien ni mention de projet. Interdits codés : réponse générique, emoji seul, copier-coller entre fils,
trop de brouillons dans une même communauté le même jour. Ces contributions comptent au ledger comme contributions sans lien.
"""
from __future__ import annotations

import difflib
import re
import subprocess
import shlex
from dataclasses import dataclass
from pathlib import Path

from .accounts import Account, Registry
from .channels.reddit import Thread
from .project import Project
from .state import Ledger, Rules
from .textutil import normalize

DEFAULT_PER_ACCOUNT = 4      # 3 à 5 par compte et par jour
DEFAULT_PER_SUB = 2          # brouillons max par communauté, par compte et par jour
MIN_WORDS = 15
MIN_CHARS = 90
MAX_CHARS = 700
SIMILARITY_MAX = 0.8

GENERIC = {
    "great post", "nice post", "good post", "great", "nice", "good", "cool", "awesome", "interesting", "amazing", "thanks",
    "thank you", "thanks for sharing", "this", "same", "agreed", "i agree", "lol", "love this", "well said", "nice work",
    "good job", "great job", "congrats", "bravo", "merci", "super", "top", "genial", "excellent", "bien dit", "merci pour le partage",
    "tres bien", "interessant", "bonne idee", "good question", "great question", "this is great", "me too", "same here",
}
_QUESTION_START = re.compile(
    r"^(how|what|why|which|where|when|who|should|can|could|does|do|is|are|any|anyone|has|have|would|comment|pourquoi|quel|quelle|quels|quelles|"
    r"est ce|peut on|qui|ou|quand|combien|y a t il|faut il|existe)\b", re.I)
_OPINION = re.compile(r"\b(thoughts|opinions?|advice|recommend\w*|suggest\w*|feedback|critique|what do you think|avis|conseils?|recommandations?|retours?)\b", re.I)
_THANKS = re.compile(r"\b(thank you|thanks to|thanks everyone|thanks all|grateful|merci)\b", re.I)
_EMPTY_BODY = re.compile(r"^\s*\[(removed|deleted)\]\s*$", re.I)
_URL = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(com|org|net|io|fr|dev|app|co)\b", re.I)
_STOP = set(normalize(
    "that this with from your have what when where which about would could should there their they them then than will just like "
    "been were being into over some more most very much many also only does done make made want need help know thing "
    "dans pour avec sans sont mais comme plus tout tous cette cela cest quel quelle quels quelles faire fait peut peuvent "
    "avoir etre vous nous leur leurs elle elles chez entre alors donc aussi").split())


@dataclass
class WarmupItem:
    account: str
    thread: Thread
    kind: str       # question | avis | merci
    contribution_id: str = ""


def answerable(thread: Thread) -> tuple[str, int] | None:
    """(type, score) si une réponse courte et utile est plausible, sinon None."""
    title = thread.title.strip()
    if len(title) < 15 or _EMPTY_BODY.match(thread.text or ""):
        return None
    norm_title = normalize(title)
    if "?" in title or _QUESTION_START.match(norm_title):
        return "question", 3
    if _OPINION.search(norm_title) or _OPINION.search(normalize(thread.text or "")[:400]):
        return "avis", 2
    if _THANKS.search(norm_title):
        return "merci", 1
    return None


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize(text))


def _significant(text: str) -> set[str]:
    return {w[:6] for w in _words(text) if len(w) >= 4 and w not in _STOP and not w.isdigit()}


def forbidden_terms(projects: dict[str, Project]) -> list[str]:
    """Tout ce qui trahirait un projet : nom, mentions déclaratives, noms de domaine des liens."""
    terms: list[str] = []
    for p in projects.values():
        terms += [p.nom] + list(p.mention)
        for link in p.liens:
            host = re.sub(r"^https?://(www\.)?", "", link).split("/")[0]
            terms.append(host)
    return [t for t in terms if t.strip()]


def check_draft(
    text: str, thread: Thread | None, banned: list[str], others: dict[str, str] | None = None, own_handles: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Contrôles mécaniques d'un brouillon de chauffe. Retourne (erreurs, avertissements)."""
    errors: list[str] = []
    warnings: list[str] = []
    body = text.strip()
    words = _words(body)
    if not words:
        return ["vide, ou emoji seul"], warnings
    core = " ".join(words)
    if core in GENERIC or (any(core.startswith(g + " ") for g in GENERIC) and len(words) < MIN_WORDS + 8):
        errors.append("réponse générique (« great post », « nice »...) : apporter une information, un avis argumenté ou une question utile")
    if len(words) < MIN_WORDS or len(body) < MIN_CHARS:
        errors.append(f"trop courte pour être utile : {len(words)} mots, {len(body)} signes (minimum {MIN_WORDS} mots, {MIN_CHARS} signes)")
    if len(body) > MAX_CHARS:
        errors.append(f"trop longue pour une chauffe : {len(body)} signes (maximum {MAX_CHARS})")
    if _URL.search(body):
        errors.append("lien ou adresse dans un brouillon de chauffe : interdit, aucun lien")
    low = normalize(body)
    for term in banned:
        if normalize(term) and normalize(term) in low:
            errors.append(f"mention d'un projet ({term}) dans un brouillon de chauffe : interdit")
            break
    for handle in own_handles or ():
        if handle in low:
            errors.append("mention d'un de tes autres comptes : jamais de réponse ni de renvoi d'un compte à l'autre")
            break
    if re.search(r"[–—]|--", body):
        errors.append("tiret cadratin, demi-cadratin ou double trait d'union (signature de texte généré)")
    if thread is not None and not (_significant(body) & _significant(thread.title + " " + thread.text[:600])):
        errors.append("aucun mot en commun avec le fil : la réponse doit porter sur ce que dit le fil")
    for name, other in (others or {}).items():
        if difflib.SequenceMatcher(None, body, other.strip()).ratio() > SIMILARITY_MAX:
            errors.append(f"quasi identique à un autre brouillon ({name}) : jamais de copier-coller d'un fil à l'autre")
    return errors, warnings


def draft_path(root: Path, day: str, account: str, thread_id: str) -> Path:
    return root / "chauffe" / day / f"{account}__{thread_id}.md"


def _sub_pool(account: Account, projects: dict[str, Project]) -> list[str]:
    if account.subs:
        return list(account.subs)
    return sorted({s for slug in account.projects if slug in projects for s in projects[slug].subs})


def warmup_subs(registry: Registry, projects: dict[str, Project], rules: Rules) -> list[str]:
    """Communautés à lire pour la chauffe : celles des comptes dont les règles sont lues."""
    seen: dict[str, str] = {}
    for account in registry.accounts.values():
        for s in _sub_pool(account, projects):
            if rules.is_read(s) and s.lower() not in registry.banned_everywhere():
                seen.setdefault(s.lower(), s)
    return sorted(seen.values(), key=str.lower)


def select_warmup(
    threads: list[Thread],
    registry: Registry,
    projects: dict[str, Project],
    ledger: Ledger,
    rules: Rules,
    day: str,
    per_account: int = DEFAULT_PER_ACCOUNT,
    per_sub: int = DEFAULT_PER_SUB,
) -> tuple[list[WarmupItem], list[str]]:
    """Choisit les fils du jour par compte et les enregistre au ledger (proposed, sans lien). Idempotent : ne complète que le manque."""
    notes: list[str] = []
    items: list[WarmupItem] = []
    own = registry.handles()
    per_account = max(1, min(per_account, 10))
    per_sub = max(1, per_sub)
    for handle in sorted(registry.accounts):
        account = registry.accounts[handle]
        done = [r for r in ledger.rows if r.account == handle and r.date == day and r.origin == "warmup" and r.status != "skipped"]
        need = per_account - len(done)
        if need <= 0:
            continue
        pool = {s.lower() for s in _sub_pool(account, projects)}
        by_sub: dict[str, list[tuple[int, Thread, str]]] = {}
        for t in threads:
            if t.sub.lower() not in pool or t.author.lower() in own or not rules.is_read(t.sub):
                continue
            found = answerable(t)
            if not found or t.url in ledger.known_threads():
                continue
            reason = registry.eligible(account, t.sub, rules.flags(t.sub), day)
            if reason:
                note = f"{handle} : {reason}"
                if note not in notes:
                    notes.append(note)
                continue
            by_sub.setdefault(t.sub.lower(), []).append((-found[1], t, found[0]))
        for lst in by_sub.values():
            lst.sort(key=lambda x: (x[0], x[1].id))
        count_sub = {k: sum(1 for r in done if r.sub.lower() == k) for k in by_sub}
        while need > 0:
            progress = False
            for sub in sorted(by_sub):
                if need <= 0:
                    break
                queue = by_sub[sub]
                if count_sub[sub] >= per_sub:
                    continue
                while queue:
                    _, thread, kind = queue.pop(0)
                    if ledger.conflict(handle, thread.sub, thread.url, day):
                        continue
                    row = ledger.add(date=day, project="", sub=thread.sub, thread_url=thread.url, kind="comment", has_link=False,
                                     status="proposed", note=f"warmup {kind}", account=handle, origin="warmup")
                    items.append(WarmupItem(handle, thread, kind, row.id))
                    count_sub[sub] += 1
                    need -= 1
                    progress = True
                    break
            if not progress:
                break
        if need > 0:
            notes.append(f"{handle} : {per_account - need} fil(s) pour {per_account} demandé(s), pas assez de fils adaptés")
    return items, notes


def run_drafter(command: str, brief: dict, timeout: int = 180) -> str | None:
    """Appelle le rédacteur externe optionnel (ex. `claude -p`) : brief JSON sur stdin, brouillon sur stdout."""
    import json

    try:
        done = subprocess.run(shlex.split(command), input=json.dumps(brief, ensure_ascii=False), capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else None


def brief_for(item: WarmupItem) -> dict:
    return {
        "task": "Rédige une réponse courte (2 à 5 phrases), réellement utile, qui répond à ce fil Reddit. Aucun lien, aucune mention de projet.",
        "type": item.kind, "subreddit": item.thread.sub, "title": item.thread.title, "text": item.thread.text[:1200],
        "contraintes": {"mots_min": MIN_WORDS, "signes_max": MAX_CHARS, "interdits": ["lien", "emoji seul", "réponse générique", "mention de projet"]},
    }
