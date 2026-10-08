"""Planification multi-projets : rotation, un projet par fil, plafond de liens, rapport Markdown du jour."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .channels.reddit import Thread
from .project import Project
from .accounts import Registry
from .state import Contribution, Ledger, Rules, WARMUP_DEFAULT, link_allowed

MAX_REPLY_CHARS = 1400


@dataclass
class Proposal:
    project: Project
    thread: Thread
    score: int
    matched: list[str]
    policy: str
    link_ok: bool
    link_reason: str
    contribution_id: str = ""
    account: str = ""


def rotation_order(projects: dict[str, Project], ledger: Ledger) -> list[Project]:
    """Le projet qui n'a pas contribué depuis le plus longtemps passe en premier (jamais contribué = d'abord)."""
    return sorted(projects.values(), key=lambda p: (ledger.last_contribution_date(p.slug), p.slug))


def plan(
    projects: dict[str, Project],
    candidates: dict[str, list[tuple[Thread, int, list[str]]]],
    ledger: Ledger,
    rules: Rules,
    max_total: int = 4,
    max_per_project: int = 2,
    warmup: int = WARMUP_DEFAULT,
    registry: Registry | None = None,
    day: str | None = None,
    notes: list[str] | None = None,
) -> list[Proposal]:
    """Répartit les fils retenus entre projets, un tour par projet, sans toucher au ledger sur disque.

    - un fil n'est jamais proposé à deux projets (ni s'il figure déjà au ledger) ;
    - au plus un lien autorisé par passe ET par compte : le plafond 1 sur 10 est lu sur le ledger, par compte (tous
      projets confondus). Sans registre de comptes, un seul compte implicite.

    Avec un registre : chaque fil reçoit un compte affecté au projet et à la communauté, jamais deux comptes dans le même
    fil ni dans la même communauté le même jour, jamais le compte d'un fil écrit par un autre de tes comptes.
    """
    day = day or date.today().isoformat()
    claimed: dict[str, str] = {}  # communauté (minuscules) -> compte, pour ce jour
    order = rotation_order(projects, ledger)
    queues = {p.slug: [c for c in candidates.get(p.slug, []) if c[0].url not in ledger.known_threads()] for p in order}
    taken: set[str] = set()
    per_project = {p.slug: 0 for p in order}
    proposals: list[Proposal] = []
    link_given: dict[str, bool] = {}
    progress = True
    while progress and len(proposals) < max_total:
        progress = False
        for project in order:
            if len(proposals) >= max_total:
                break
            if per_project[project.slug] >= max_per_project:
                continue
            queue = queues[project.slug]
            while queue and queue[0][0].url in taken:
                queue.pop(0)
            if not queue:
                continue
            thread, score, matched = queue.pop(0)
            taken.add(thread.url)
            policy = rules.policy(thread.sub)
            flags = rules.flags(thread.sub)
            account = ""
            if registry:
                account, why = _pick_account(registry, ledger, project, thread, policy, flags, warmup, day, claimed)
                if not account:
                    if notes is not None:
                        notes.append(f"r/{thread.sub} fil {thread.id} : aucun compte possible ({why})")
                    continue
                claimed[thread.sub.lower()] = account
            ok, reason = link_allowed(ledger, policy, warmup, account or None, flags, day)
            if ok and link_given.get(account):
                ok, reason = False, "un seul lien autorisé par passe et par compte"
            link_given[account] = link_given.get(account, False) or ok
            proposals.append(Proposal(project, thread, score, matched, policy, ok, reason, account=account))
            per_project[project.slug] += 1
            progress = True
    return proposals


def _pick_account(registry, ledger, project, thread, policy, flags, warmup, day, claimed):
    """Compte pour ce fil, ou ("", raison). Préfère un compte qui peut poser un lien, puis le moins chargé."""
    if thread.author and thread.author.lower() in registry.handles():
        return "", "fil écrit par un de tes comptes : jamais de réponse d'un compte à l'autre"
    reasons: list[str] = []
    options = []
    for handle in sorted(registry.accounts):
        account = registry.accounts[handle]
        why = registry.eligible(account, thread.sub, flags, day, project.slug)
        if not why:
            why = ledger.conflict(handle, thread.sub, thread.url, day)
        if not why and claimed.get(thread.sub.lower(), handle) != handle:
            why = f"le compte {claimed[thread.sub.lower()]} est déjà dans r/{thread.sub} aujourd'hui"
        if why:
            reasons.append(f"{handle} : {why}")
            continue
        ok, _ = link_allowed(ledger, policy, warmup, handle, flags, day)
        options.append((not ok, len(ledger.counted(handle)), handle))
    if not options:
        return "", " ; ".join(reasons) or "aucun compte enregistré"
    return min(options)[2], ""


def record_proposals(proposals: list[Proposal], ledger: Ledger, today: str | None = None) -> None:
    for p in proposals:
        row = ledger.add(
            date=today or date.today().isoformat(), project=p.project.slug, sub=p.thread.sub,
            thread_url=p.thread.url, kind="comment", has_link=False, status="proposed", note=f"score {p.score}", account=p.account, origin="promo",
        )
        p.contribution_id = row.id


def _quote(text: str, limit: int = 400) -> str:
    cut = text[:limit] + ("…" if len(text) > limit else "")
    return "\n".join("> " + line for line in (cut or "(pas de texte)").splitlines())


def render_report(
    day: str,
    proposals: list[Proposal],
    unread: dict[str, list[str]],
    ledger: Ledger,
    replies_dir: Path | None = None,
    warnings: list[str] | None = None,
) -> str:
    with_link, total = ledger.ratio()
    lines = [f"# Promotion du {day}", ""]
    lines.append(f"Ratio global du compte : {with_link} contribution(s) avec lien sur {total} comptée(s) (plafond : 1 sur 10, tous projets).")
    lines.append("Rien n'est publié par l'outil : tu relis, tu copies, tu publies toi-même sous ton compte.")
    lines.append("")
    if warnings:
        lines += ["## Avertissements", ""] + [f"- {w}" for w in warnings] + [""]
    if not proposals:
        lines += ["## Fils retenus", "", "Aucun fil retenu aujourd'hui (rien de pertinent, ou tout déjà traité).", ""]
    for index, p in enumerate(proposals, start=1):
        lines += [
            f"## {index}. {p.project.nom} : r/{p.thread.sub}" + (f" (compte {p.account})" if p.account else ""),
            "",
            f"- Fil : {p.thread.url}",
            f"- Titre : {p.thread.title}",
            f"- Score mots-clés : {p.score} ({', '.join(p.matched)})",
            f"- Identifiant ledger : {p.contribution_id or 'non enregistré'}",
            f"- Lien vers le projet : {'AUTORISÉ si une page répond vraiment au fil' if p.link_ok else 'NON'} ({p.link_reason})",
            "",
            _quote(p.thread.text),
            "",
            "### Brief de rédaction",
            "",
            f"- Pitch : {p.project.pitch}",
            f"- Public : {p.project.public}",
            f"- Langue(s) : {', '.join(p.project.langues)} (réponse en français : charger le skill `redaction`)",
            "- Faits affirmables (seuls autorisés) :",
        ]
        lines += [f"  - {f.text} (source : {f.source})" for f in p.project.faits] or ["  - aucun fait sourcé dans la fiche : ne rien affirmer"]
        if p.link_ok:
            lines += [f"- Lien à utiliser : {p.project.main_link}", f"- Mention obligatoire avec le lien (une de) : {' / '.join(p.project.mention)}"]
        else:
            lines += ["- Aucun lien, aucune mention du site : répondre pour aider, rien d'autre."]
        lines += [f"- Longueur maximale : {MAX_REPLY_CHARS} signes", ""]
        reply = (replies_dir / f"{p.thread.id}.md") if replies_dir else None
        if reply and reply.exists():
            lines += ["### Réponse proposée", "", reply.read_text(encoding="utf-8").strip(), ""]
        else:
            lines += ["### Réponse proposée", "", f"À rédiger en 3 passes (brouillon, relecture séparée, version finale) puis à déposer dans `reponses/{p.thread.id}.md`.", ""]
    if unread:
        lines += ["## Communautés à lire d'abord [NV]", ""]
        lines += ["Règle non lue : aucun repérage, aucune inscription. Lire l'onglet Règles sur le site de Reddit puis `promo.py rules`.", ""]
        for slug, subs in sorted(unread.items()):
            lines.append(f"- {slug} : " + ", ".join(f"r/{s}" for s in subs))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_discovery(project: Project, measured: list, warnings: list[str], day: str) -> str:
    lines = [f"# Communautés candidates pour {project.nom} ({day})", ""]
    lines += ["Taille et activité viennent de l'archive publique Arctic Shift. La citation de la colonne latérale peut dater de plusieurs mois et ne vaut JAMAIS lecture de l'onglet Règles : tout reste [NV] tant que `promo.py rules` n'a pas enregistré la règle lue.", ""]
    if warnings:
        lines += [f"- {w}" for w in warnings] + [""]
    kept = [m for m in measured if not m.excluded]
    out = [m for m in measured if m.excluded]
    lines += ["| Sub | Abonnés | Fils/jour | Sur le sujet | Note /100 | Autopromotion (colonne latérale) | Statut |", "|---|---|---|---|---|---|---|"]
    for m in sorted(kept, key=lambda m: -m.rank):
        subs = f"{m.subscribers:,}".replace(",", " ") if m.subscribers else "inconnu"
        quote = {"forbidden": "interdite : « %s »", "mentioned": "citée : « %s »"}.get(m.promo_verdict, "aucune phrase trouvée")
        quote = quote % (m.promo_quote or "") if "%s" in quote else quote
        lines.append(f"| r/{m.sub} | {subs} | {m.per_day:.1f} | {m.relevant_share:.0%} | {m.rank} | {quote.replace('|', '/')} | [NV] règle à lire |")
    if out:
        lines += ["", "Écartées :", ""] + [f"- r/{m.sub} : {m.excluded}" for m in out]
    return "\n".join(lines) + "\n"
