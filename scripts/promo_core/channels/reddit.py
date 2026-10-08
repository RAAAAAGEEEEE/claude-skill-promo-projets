"""Reddit en lecture seule : flux RSS publics (repérage, découverte) et archive Arctic Shift (taille, activité).

Aucune API Reddit, aucun jeton, aucune écriture. Reddit tolère environ une requête anonyme par minute :
l'espacement est de 65 s et la passe s'arrête au premier HTTP 429.
"""
from __future__ import annotations

import html
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable
from xml.etree import ElementTree as ET

from ..project import Project, SUB_RE
from ..relevance import MIN_THREAD_SCORE, score_thread
from ..textutil import sentences, strip_tags

FEED_DELAY_S = 65
ARCHIVE_DELAY_S = 3
ARCHIVE = "https://arctic-shift.photon-reddit.com/api"
ATOM = "{http://www.w3.org/2005/Atom}"
MIN_SUBSCRIBERS = 500
MAX_IDLE_DAYS = 30
MIN_THREADS_PER_DAY = 0.3


def user_agent() -> str:
    return os.environ.get("PROMO_USER_AGENT") or "promo-projets/0.1 (lecture seule, aucune publication)"


# Un « fetcher » reçoit une URL et retourne (statut HTTP, corps texte). Injectable pour les tests.
Fetcher = Callable[[str], "tuple[int, str]"]


def http_get(url: str) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent()})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, ""


@dataclass(frozen=True)
class Thread:
    id: str
    sub: str
    title: str
    url: str
    text: str


_THREAD_URL = re.compile(r"^https://(?:www\.|old\.)?reddit\.com/r/([^/]+)/comments/([a-z0-9]+)/", re.I)
_SUB_URL = re.compile(r"^https://(?:www\.)?reddit\.com/r/([^/]+)/?$", re.I)


def _entries(xml: str) -> list[ET.Element]:
    try:
        return list(ET.fromstring(xml).iter(f"{ATOM}entry"))
    except ET.ParseError:
        return []


def _entry_fields(entry: ET.Element) -> tuple[str, str, str]:
    link = entry.find(f"{ATOM}link")
    title = entry.findtext(f"{ATOM}title") or ""
    content = entry.findtext(f"{ATOM}content") or ""
    return (link.get("href", "") if link is not None else ""), title, content


def parse_thread_feed(xml: str) -> list[Thread]:
    threads: list[Thread] = []
    for entry in _entries(xml):
        url, title, content = _entry_fields(entry)
        match = _THREAD_URL.match(html.unescape(url))
        if not match or not title.strip():
            continue
        text = re.sub(r"\s*\[link\]\s*\[comments\]\s*$", "", strip_tags(html.unescape(content)))
        threads.append(Thread(match.group(2), match.group(1), strip_tags(title), html.unescape(url), text[:2000]))
    return threads


@dataclass
class SubCandidate:
    name: str
    title: str
    description: str
    mentions: int = 1


def parse_subreddit_feed(xml: str) -> list[SubCandidate]:
    out: list[SubCandidate] = []
    for entry in _entries(xml):
        url, title, content = _entry_fields(entry)
        match = _SUB_URL.match(html.unescape(url))
        if not match or not SUB_RE.match(match.group(1)) or match.group(1).startswith("u_"):
            continue
        description = re.sub(r"\s*\[link\]\s*$", "", strip_tags(html.unescape(content)))[:600]
        out.append(SubCandidate(match.group(1), strip_tags(title), description))
    return out


def build_query(project: Project, limit: int = 4) -> str:
    """Requête de recherche : les mots-clés les plus lourds (hors regex), séparés par OR."""
    words = [k.keyword for k in sorted(project.mots_cles, key=lambda k: -k.weight) if k.mode != "regex"][:limit]
    return " OR ".join(f'"{w}"' if " " in w else w for w in words)


def fetch_threads(
    specs: list[tuple[str, str]], fetch: Fetcher = http_get, sleep: Callable[[float], None] = time.sleep, delay: float = FEED_DELAY_S
) -> tuple[list[Thread], list[str]]:
    """Lit un flux de recherche par (sub, requête). Retourne (fils, avertissements). S'arrête au premier 429."""
    out: list[Thread] = []
    warnings: list[str] = []
    for index, (sub, query) in enumerate(specs):
        if index:
            sleep(delay)
        url = f"https://www.reddit.com/r/{sub}/search.rss?q={urllib.parse.quote(query)}&restrict_sr=1&sort=new"
        status, body = fetch(url)
        if status == 429:
            warnings.append(f"HTTP 429 sur r/{sub} : la passe s'arrête ici (relancer plus tard)")
            break
        if status != 200:
            warnings.append(f"r/{sub} illisible (statut {status})")
            continue
        out.extend(parse_thread_feed(body))
    return out, warnings


# ---------------------------------------------------------------------------
# Découverte de communautés
# ---------------------------------------------------------------------------


def discover(
    queries: list[str], fetch: Fetcher = http_get, sleep: Callable[[float], None] = time.sleep, delay: float = FEED_DELAY_S
) -> tuple[list[SubCandidate], list[str]]:
    found: dict[str, SubCandidate] = {}
    warnings: list[str] = []
    for index, query in enumerate(queries):
        if index:
            sleep(delay)
        status, body = fetch(f"https://www.reddit.com/subreddits/search.rss?q={urllib.parse.quote(query)}")
        if status == 429:
            warnings.append(f"HTTP 429 sur la requête « {query} » : découverte arrêtée")
            break
        if status != 200:
            warnings.append(f"requête « {query} » refusée (statut {status})")
            continue
        for sub in parse_subreddit_feed(body):
            known = found.get(sub.name.lower())
            if known:
                known.mentions += 1
            else:
                found[sub.name.lower()] = sub
    return sorted(found.values(), key=lambda s: -s.mentions), warnings


@dataclass
class ArchiveStats:
    subscribers: int | None
    over18: bool
    threads: list[tuple[str, str, float]]  # (titre, texte, created_utc)
    sidebar: str
    sidebar_at: float | None


def parse_archive(posts: object, subreddit: object) -> ArchiveStats:
    rows = posts.get("data", []) if isinstance(posts, dict) else []
    threads: list[tuple[str, str, float]] = []
    subscribers: int | None = None
    for post in rows:
        if not isinstance(post, dict) or not isinstance(post.get("title"), str) or not isinstance(post.get("created_utc"), (int, float)):
            continue
        selftext = post.get("selftext") if isinstance(post.get("selftext"), str) else ""
        threads.append((post["title"], selftext[:2000], float(post["created_utc"])))
        if subscribers is None and isinstance(post.get("subreddit_subscribers"), int):
            subscribers = post["subreddit_subscribers"]
    data = subreddit.get("data", []) if isinstance(subreddit, dict) else []
    record = data[0] if data and isinstance(data[0], dict) else {}
    if subscribers is None and isinstance(record.get("subscribers"), int):
        subscribers = record["subscribers"]
    sidebar = "\n".join(str(record[k]) for k in ("public_description", "description") if isinstance(record.get(k), str) and record[k])
    retrieved = record.get("retrieved_on")
    return ArchiveStats(subscribers, record.get("over18") is True, threads, sidebar, float(retrieved) if isinstance(retrieved, (int, float)) else None)


def fetch_archive(sub: str, fetch: Fetcher = http_get, sleep: Callable[[float], None] = time.sleep) -> ArchiveStats | None:
    status, body = fetch(f"{ARCHIVE}/posts/search?subreddit={urllib.parse.quote(sub)}&sort=desc&limit=100")
    if status != 200:
        return None
    try:
        posts = json.loads(body)
    except json.JSONDecodeError:
        return None
    sleep(ARCHIVE_DELAY_S)
    status, body = fetch(f"{ARCHIVE}/subreddits/search?subreddit={urllib.parse.quote(sub)}&limit=1")
    try:
        record = json.loads(body) if status == 200 else None
    except json.JSONDecodeError:
        record = None
    return parse_archive(posts, record)


_FORBIDS = re.compile(
    r"\b(no|not allowed|do not|don't|never|prohibited|banned|forbidden|without)\b[^.\n]{0,60}\b(self[- ]?promo\w*|advertis\w*|spam\w*|promot\w*|solicit\w*)"
    r"|\b(self[- ]?promo\w*|advertis\w*|spam\w*)\b[^.\n]{0,40}\b(not allowed|prohibited|banned|forbidden|removed)",
    re.I,
)
_MENTIONS = re.compile(r"\b(self[- ]?promo\w*|advertis\w*|spam\w*|promotion\w*|promotional)\b", re.I)


def find_promo_rule(sidebar: str) -> tuple[str, str | None]:
    """(verdict, citation) tirés de la colonne latérale archivée. Ne vaut jamais lecture de l'onglet Règles."""
    lines = sentences(sidebar)
    hit = next((s for s in lines if _FORBIDS.search(s)), None)
    if hit:
        return "forbidden", hit[:220]
    hit = next((s for s in lines if _MENTIONS.search(s)), None)
    return ("mentioned", hit[:220]) if hit else ("unknown", None)


def threads_per_day(times: list[float]) -> float:
    if len(times) < 2:
        return 0.0
    span = (max(times) - min(times)) / 86400
    return len(times) / span if span > 0 else float(len(times))


@dataclass
class Measured:
    sub: str
    subscribers: int | None
    relevant_share: float
    per_day: float
    idle_days: float | None
    rank: float
    promo_verdict: str
    promo_quote: str | None
    sidebar_age_days: float | None
    excluded: str | None
    mentions: int = 0
    notes: list[str] = field(default_factory=list)


def rank_score(relevant_share: float, per_day: float, subscribers: int | None) -> float:
    """0 à 100 : pertinence (50, pleine à 50 % de fils sur le sujet), activité (25, pleine à 5 fils/jour), taille (25, de 500 à 500 000 abonnés)."""
    size = min(1.0, math.log10(subscribers / MIN_SUBSCRIBERS) / 3) if subscribers and subscribers > MIN_SUBSCRIBERS else 0.0
    return round(50 * min(1.0, relevant_share / 0.5) + 25 * min(1.0, per_day / 5) + 25 * size, 1)


def measure(project: Project, candidate: SubCandidate, stats: ArchiveStats | None, now: float | None = None) -> Measured:
    now = now if now is not None else time.time()
    if stats is None:
        return Measured(candidate.name, None, 0, 0, None, 0, "unknown", None, None, "archive illisible : taille et activité inconnues", candidate.mentions)
    times = [t for _, _, t in stats.threads]
    relevant = sum(1 for title, text, _ in stats.threads if score_thread(title, text, project.mots_cles, project.mots_exclus).score >= MIN_THREAD_SCORE)
    share = relevant / len(stats.threads) if stats.threads else 0.0
    per_day = threads_per_day(times)
    idle = (now - max(times)) / 86400 if times else None
    verdict, quote = find_promo_rule(stats.sidebar)
    age = (now - stats.sidebar_at) / 86400 if stats.sidebar_at else None
    excluded: str | None = None
    if stats.over18:
        excluded = "contenu adulte"
    elif stats.subscribers is not None and stats.subscribers < MIN_SUBSCRIBERS:
        excluded = f"moins de {MIN_SUBSCRIBERS} abonnés"
    elif idle is None or idle > MAX_IDLE_DAYS:
        excluded = f"aucun fil depuis plus de {MAX_IDLE_DAYS} jours"
    elif per_day < MIN_THREADS_PER_DAY:
        excluded = "moins d'un fil tous les trois jours"
    elif relevant == 0:
        excluded = "aucun fil sur le sujet du projet"
    return Measured(candidate.name, stats.subscribers, share, per_day, idle, rank_score(share, per_day, stats.subscribers), verdict, quote, age, excluded, candidate.mentions)


def score_threads(project: Project, threads: list[Thread]) -> list[tuple[Thread, int, list[str]]]:
    kept: list[tuple[Thread, int, list[str]]] = []
    for thread in threads:
        result = score_thread(thread.title, thread.text, project.mots_cles, project.mots_exclus)
        if result.score >= MIN_THREAD_SCORE:
            kept.append((thread, result.score, result.matched))
    return sorted(kept, key=lambda item: -item[1])
