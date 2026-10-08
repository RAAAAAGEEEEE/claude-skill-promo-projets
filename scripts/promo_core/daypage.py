"""Page HTML du jour (le « dernier clic » appartient à l'humain) et petit serveur local optionnel.

La page liste, par compte, les brouillons : texte, communauté, lien du fil, boutons Copier, Ouvrir le fil et Marquer publié.
Aucun bouton ne publie quoi que ce soit : « Marquer publié » ne fait qu'inscrire au ledger ce que l'humain a déjà publié.
Un seul fichier, aucune dépendance, aucun appel réseau depuis la page.
"""
from __future__ import annotations

import html
import json
import re
import secrets
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .accounts import Registry
from .state import Ledger

_THREAD_ID = re.compile(r"/comments/([a-z0-9]+)/", re.I)
_SAFE_URL = re.compile(r"^https://(www\.|old\.)?reddit\.com/r/[A-Za-z0-9_]+/comments/[a-z0-9]+/[^\s\"'<>]*$", re.I)
CACHE_MAX = 500


def thread_id(url: str) -> str:
    m = _THREAD_ID.search(url)
    return m.group(1) if m else ""


# --- cache des fils (titre, extrait) : le ledger ne garde que l'adresse -------------------------------------------------

def load_cache(path: Path) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(path: Path, cache: dict[str, dict]) -> None:
    items = list(cache.items())[-CACHE_MAX:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(items), ensure_ascii=False, indent=1), encoding="utf-8")


def remember(cache: dict[str, dict], thread) -> None:
    cache[thread.url] = {"id": thread.id, "sub": thread.sub, "title": thread.title, "text": thread.text[:600], "author": thread.author}


# --- entrées de la page -----------------------------------------------------------------------------------------------

@dataclass
class Entry:
    id: str
    account: str
    origin: str
    sub: str
    url: str
    title: str
    excerpt: str
    status: str
    draft: str | None
    has_link: bool
    note: str
    problem: str = ""


def build_entries(root: Path, day: str, ledger: Ledger, cache: dict[str, dict]) -> list[Entry]:
    entries: list[Entry] = []
    for row in ledger.rows:
        if row.date != day or row.status == "skipped" or row.origin not in ("promo", "warmup"):
            continue
        tid = thread_id(row.thread_url)
        meta = cache.get(row.thread_url, {})
        if row.origin == "warmup":
            path = root / "chauffe" / day / f"{row.account}__{tid}.md"
        else:
            path = root / "reponses" / f"{tid}.md"
        draft = path.read_text(encoding="utf-8").strip() if path.exists() else None
        entries.append(Entry(row.id, row.account, row.origin, row.sub, row.thread_url, meta.get("title", "(titre non conservé)"),
                             meta.get("text", ""), row.status, draft or None, row.has_link, row.note))
    return entries


def command_for(entry_id: str, root: Path, script: Path, default_root: Path | None) -> str:
    base = f'python "{script}"'
    if default_root is None or root.resolve() != default_root.resolve():
        base += f' --data-dir "{root}"'
    return f"{base} ledger add --id {entry_id}"


_CSS = """
:root{--bg:#fafaf7;--fg:#1d1d1b;--mut:#6b6b66;--card:#fff;--line:#e2e0d8;--acc:#1f5fbf;--ok:#1d7a46;--warn:#9a5b00}
@media(prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ecebe6;--mut:#a09f98;--card:#201f1d;--line:#34332f;--acc:#7fb0ff;--ok:#5cc88b;--warn:#e0a24a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:20px 16px 60px}h1{font-size:1.4rem;margin:0 0 4px}h2{font-size:1.15rem;margin:32px 0 4px}
.sub{color:var(--mut);font-size:.9rem}.banner{border:1px solid var(--line);background:var(--card);border-radius:8px;padding:10px 12px;margin:12px 0}
.card{border:1px solid var(--line);background:var(--card);border-radius:10px;padding:14px;margin:12px 0}
.card.done{opacity:.6}.meta{font-size:.85rem;color:var(--mut)}.tag{display:inline-block;border:1px solid var(--line);border-radius:99px;padding:0 8px;font-size:.78rem;margin-right:6px}
.tag.promo{color:var(--warn)}pre.draft{white-space:pre-wrap;word-wrap:break-word;font:inherit;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px;margin:10px 0}
.todo{color:var(--warn)}.row{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
button,a.btn{font:inherit;font-size:.9rem;padding:7px 12px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer;text-decoration:none}
button:hover,a.btn:hover{border-color:var(--acc)}button.primary{background:var(--acc);color:var(--bg);border-color:var(--acc)}
code.cmd{display:block;margin-top:8px;padding:8px;background:var(--bg);border:1px solid var(--line);border-radius:6px;word-break:break-all;font-size:.82rem}
.hidden{display:none}.state{color:var(--ok);font-size:.9rem;margin-top:6px}
"""

_JS = """
function copyText(text,btn){
  var done=function(){var o=btn.textContent;btn.textContent='Copié';setTimeout(function(){btn.textContent=o},1500)};
  if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(text).then(done,function(){fallback(text,done)})}else{fallback(text,done)}
}
function fallback(text,done){var t=document.createElement('textarea');t.value=text;document.body.appendChild(t);t.select();try{document.execCommand('copy');done()}catch(e){}document.body.removeChild(t)}
document.addEventListener('click',function(ev){
  var b=ev.target.closest('button[data-act]');if(!b)return;var card=b.closest('.card');var act=b.dataset.act;
  if(act==='copy'){copyText(card.querySelector('pre.draft').textContent,b)}
  if(act==='cmd'){var c=card.querySelector('code.cmd');c.classList.remove('hidden');copyText(c.textContent,b)}
  if(act==='publish'){
    fetch('/publish',{method:'POST',headers:{'Content-Type':'application/json','X-Promo-Token':document.body.dataset.token},body:JSON.stringify({id:card.dataset.id})})
      .then(function(r){return r.json()}).then(function(j){var s=card.querySelector('.state');s.textContent=j.ok?'Enregistré au ledger : publié':'Refusé : '+(j.error||'erreur');if(j.ok){card.classList.add('done');b.disabled=true}})
      .catch(function(){card.querySelector('.state').textContent='Serveur local injoignable'});
  }
});
"""


def _entry_html(e: Entry, cmd: str, serve: bool) -> str:
    esc = html.escape
    link = (f'<a class="btn" href="{esc(e.url, quote=True)}" target="_blank" rel="noopener noreferrer">Ouvrir le fil</a>'
            if _SAFE_URL.match(e.url) else f'<span class="meta">fil : {esc(e.url)}</span>')
    tag = '<span class="tag promo">réponse de promo</span>' if e.origin == "promo" else '<span class="tag">chauffe</span>'
    link_tag = '<span class="tag promo">contient un lien</span>' if e.has_link else ""
    if e.draft:
        body = f'<pre class="draft">{esc(e.draft)}</pre>'
        buttons = '<button class="primary" data-act="copy">Copier</button>'
    else:
        why = f"Brouillon refusé : {esc(e.problem)}" if e.problem else "Brouillon à rédiger (voir le brief dans le rapport du jour). Il apparaîtra ici au prochain passage."
        body = f'<p class="todo">{why}</p><pre class="draft hidden"></pre>'
        buttons = ""
    done = e.status == "published"
    publish = ('<button data-act="publish">Marquer publié</button>' if serve else '<button data-act="cmd">Marquer publié</button>') if not done else ""
    state = '<div class="state">Publié</div>' if done else '<div class="state"></div>'
    return (
        f'<article class="card{" done" if done else ""}" data-id="{esc(e.id, quote=True)}">'
        f'<div>{tag}{link_tag}<span class="meta">r/{esc(e.sub)} · {esc(e.id)}</span></div>'
        f'<h3 style="margin:6px 0 2px;font-size:1rem">{esc(e.title)}</h3>'
        f'<div class="meta">{esc(e.excerpt[:220])}</div>{body}'
        f'<div class="row">{buttons}{link}{publish}</div>'
        f'<code class="cmd hidden">{esc(cmd)}</code>{state}</article>'
    )


def render_page(day: str, entries: list[Entry], registry: Registry, ledger: Ledger, root: Path, script: Path,
                default_root: Path | None = None, token: str | None = None) -> str:
    serve = token is not None
    esc = html.escape
    parts = [
        "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
        f"<title>Promotion du {esc(day)}</title><style>{_CSS}</style></head>",
        f'<body{f" data-token={chr(34)}{esc(token)}{chr(34)}" if serve else ""}><main>',
        f"<h1>Promotion du {esc(day)}</h1>",
        '<div class="banner">Rien n\'est publié par cet outil : tu copies, tu ouvres le fil, tu publies toi-même avec le bon compte, puis tu marques publié. '
        + ("Mode serveur local : « Marquer publié » enregistre au ledger." if serve else "Mode fichier : « Marquer publié » affiche la commande à copier dans ton terminal.")
        + "</div>",
    ]
    handles = sorted({e.account for e in entries} | set(registry.accounts))
    for handle in handles:
        mine = [e for e in entries if e.account == handle]
        if not mine and handle not in registry.accounts:
            continue
        acc = registry.accounts.get(handle)
        with_link, total = ledger.ratio(handle)
        detail = ""
        if acc:
            detail = f"{esc(acc.role or 'compte')} · karma {acc.karma} · {acc.age_days(day)} j · liens : {with_link} sur {total} (plafond 1 sur 10)"
        parts.append(f'<h2>{"u/" + esc(handle) if handle else "Compte non précisé"}</h2><div class="sub">{detail}</div>')
        if not mine:
            parts.append('<p class="meta">Rien à faire aujourd\'hui pour ce compte.</p>')
        for e in mine:
            parts.append(_entry_html(e, command_for(e.id, root, script, default_root), serve))
    if not entries:
        parts.append("<p>Aucun brouillon aujourd'hui.</p>")
    parts.append(f"<script>{_JS}</script></main></body></html>")
    return "".join(parts)


# --- publication enregistrée ------------------------------------------------------------------------------------------

def mark_published(ledger_path: Path, ident: str) -> tuple[bool, str]:
    ledger = Ledger(ledger_path)
    try:
        row = ledger.find(ident)
    except KeyError:
        return False, f"contribution inconnue : {ident}"
    if row.status == "skipped":
        return False, "contribution écartée"
    row.status = "published"
    ledger.save()
    return True, row.id


def make_server(root: Path, day: str, script: Path, port: int = 8765, default_root: Path | None = None, builder=None) -> ThreadingHTTPServer:
    """Serveur local, 127.0.0.1 seulement. POST /publish exige le jeton de la page (anti-CSRF) et un Host local."""
    token = secrets.token_urlsafe(16)
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence
            pass

        def _local_host(self) -> bool:
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._local_host() or self.path.split("?")[0] != "/":
                return self._send(404, b"not found", "text/plain")
            self._send(200, builder(token).encode("utf-8"), "text/html; charset=utf-8")

        def do_POST(self):
            if not self._local_host() or self.path != "/publish":
                return self._send(404, b"not found", "text/plain")
            if not secrets.compare_digest(self.headers.get("X-Promo-Token") or "", token):
                return self._send(403, json.dumps({"ok": False, "error": "jeton invalide"}).encode(), "application/json")
            try:
                length = int(self.headers.get("Content-Length") or 0)
                ident = str(json.loads(self.rfile.read(min(length, 4096))).get("id", ""))
            except (ValueError, json.JSONDecodeError):
                return self._send(400, json.dumps({"ok": False, "error": "requête illisible"}).encode(), "application/json")
            with lock:
                ok, info = mark_published(root / "ledger.csv", ident)
            self._send(200 if ok else 409, json.dumps({"ok": ok, "error": None if ok else info}).encode(), "application/json")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.token = token  # type: ignore[attr-defined]
    return server
