#!/usr/bin/env python3
"""promo-projets : repérage Reddit multi-projets, ledger commun, contrôle des réponses. Rien n'est publié par l'outil."""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from promo_core import daypage, telegram, warmup  # noqa: E402
from promo_core.accounts import AccountError, Registry, clean_handle  # noqa: E402
from promo_core.channels import reddit  # noqa: E402
from promo_core.ruleflags import derive_policy, describe, parse_flags  # noqa: E402
from promo_core.rulesfetch import fetch_rules  # noqa: E402
from promo_core.checkreply import check_reply, project_links_in  # noqa: E402
from promo_core.project import ProjectError, load_projects, validate_portfolio  # noqa: E402
from promo_core.scan import plan, record_proposals, render_discovery, render_report  # noqa: E402
from promo_core.state import POLICIES, WARMUP_DEFAULT, Ledger, Rules, data_dir, link_allowed  # noqa: E402

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "projets"


def _paths(root: Path) -> dict[str, Path]:
    return {
        "projets": root / "projets", "ledger": root / "ledger.csv", "rules": root / "communautes.json",
        "sorties": root / "sorties", "reponses": root / "reponses", "comptes": root / "comptes.json",
        "fils": root / "fils.json", "chauffe": root / "chauffe",
    }


def cmd_init(args: argparse.Namespace, root: Path, **_: object) -> int:
    p = _paths(root)
    for key in ("projets", "sorties", "reponses"):
        p[key].mkdir(parents=True, exist_ok=True)
    if not any(p["projets"].glob("*.md")):
        for example in EXAMPLES.glob("*.md"):
            shutil.copy(example, p["projets"] / example.name)
    Ledger(p["ledger"]).save()
    Rules(p["rules"]).save()
    Registry(p["comptes"]).save()
    print(f"dossier de données prêt : {root}")
    print("fiches d'exemple copiées dans projets/ : les remplacer par tes vrais projets (faits sourcés seulement).")
    return 0


def _load(root: Path):
    p = _paths(root)
    projects = load_projects(p["projets"])
    return projects, Ledger(p["ledger"]), Rules(p["rules"]), p


def cmd_check(args: argparse.Namespace, root: Path, **_: object) -> int:
    projects, ledger, rules, _p = _load(root)
    errors = validate_portfolio(projects)
    for slug, project in projects.items():
        if not project.faits:
            print(f"AVERTISSEMENT {slug} : aucun fait sourcé, les réponses ne pourront rien affirmer")
        unread = [s for s in project.subs if not rules.is_read(s)]
        if unread:
            print(f"[NV] {slug} : règles non lues pour " + ", ".join(f"r/{s}" for s in unread))
    for error in errors:
        print(f"ERREUR {error}")
    registry = Registry(_p["comptes"])
    for handle, account in sorted(registry.accounts.items()):
        if not account.subs and not account.projects:
            print(f"AVERTISSEMENT compte {handle} : aucune affectation (projets ni communautés), il ne recevra rien")
        for slug in account.projects:
            if slug not in projects:
                errors.append(f"compte {handle} : projet inconnu {slug}")
    with_link, total = ledger.ratio()
    print(f"{len(projects)} projet(s), {len(registry.accounts)} compte(s), ledger : {with_link} lien(s) sur {total} contribution(s) comptée(s)")
    return 1 if errors else 0


def cmd_discover(args: argparse.Namespace, root: Path, fetch=reddit.http_get, sleep=time.sleep, **_: object) -> int:
    projects, _ledger, _rules, p = _load(root)
    project = projects[args.project]
    queries = project.requetes_communautes or [k.keyword for k in sorted(project.mots_cles, key=lambda k: -k.weight) if k.mode != "regex"][:6]
    candidates, warnings = reddit.discover(queries[:8], fetch, sleep)
    measured = []
    for candidate in candidates[:30]:
        stats = reddit.fetch_archive(candidate.name, fetch, sleep)
        measured.append(reddit.measure(project, candidate, stats))
    p["sorties"].mkdir(parents=True, exist_ok=True)
    out = p["sorties"] / f"decouverte-{project.slug}-{args.date}.md"
    out.write_text(render_discovery(project, measured, warnings, args.date), encoding="utf-8")
    print(f"{len(candidates)} communauté(s) trouvée(s), rapport : {out}")
    return 0


def _known_sub(sub: str, projects: dict, registry: Registry) -> tuple[bool, str | None]:
    owners = [s for s, pr in projects.items() if sub.lower() in (x.lower() for x in pr.subs)]
    in_accounts = any(sub.lower() in (x.lower() for x in a.subs) for a in registry.accounts.values())
    return bool(owners or in_accounts), (owners[0] if owners else None)


def _store_rules_text(rules: Rules, sub: str, text: str, source: str, owner: str | None) -> str:
    flags = parse_flags(text)
    policy = rules.record_text(sub, text, source, flags, derive_policy(flags), owner)
    rules.save()
    print(f"r/{sub} : règles enregistrées ({source}, {len(text)} signes, datées). Drapeaux : {describe(flags)}.")
    print(f"politique retenue : {policy}" + ("" if policy == "declaree-ok" else " (aucun lien tant qu'elle n'est pas `declaree-ok`)"))
    if policy == "non-verifie":
        print("le texte ne dit rien de clair sur l'autopromotion : chauffe possible, aucun lien. Pour autoriser un lien, relire la règle puis "
              "`promo.py rules <sub> --policy declaree-ok --quote \"<phrase>\"`.")
    return policy


def cmd_rules(args: argparse.Namespace, root: Path, fetch=reddit.http_get, sleep=time.sleep, **_: object) -> int:
    projects, _ledger, rules, p = _load(root)
    registry = Registry(p["comptes"])
    words = args.words
    action = words[0] if words[0] in ("fetch", "import") and len(words) == 2 else None
    sub = (words[1] if action else words[0]).removeprefix("r/")
    known, owner = _known_sub(sub, projects, registry)
    if not known:
        print(f"ERREUR r/{sub} ne figure dans aucune fiche projet ni aucun compte : l'ajouter à `subs` d'une fiche ou `accounts assign` d'abord")
        return 1
    if action == "fetch":
        text, source, warnings = fetch_rules(sub, fetch, sleep)
        for w in warnings:
            print(f"AVERTISSEMENT {w}")
        if not text:
            print(f"ERREUR règles de r/{sub} illisibles par le réseau. Méthode : ouvrir https://old.reddit.com/r/{sub}/about/rules dans le navigateur "
                  f"intégré, get_page_text, enregistrer le texte dans un fichier, puis `promo.py rules import {sub} --from-text <fichier>`.")
            return 1
        _store_rules_text(rules, sub, text, source, owner)
        return 0
    if action == "import":
        if not args.from_text:
            print("ERREUR rules import demande --from-text <fichier>")
            return 1
        try:
            text = Path(args.from_text).read_text(encoding="utf-8")
        except OSError:
            print(f"ERREUR fichier illisible : {args.from_text}")
            return 1
        if len(text.strip()) < 20:
            print("ERREUR texte des règles vide ou trop court : rien enregistré, la communauté reste [NV]")
            return 1
        _store_rules_text(rules, sub, text, "import (navigateur)", owner)
        return 0
    if not args.policy or not args.quote:
        print("ERREUR forme : rules fetch <sub> | rules import <sub> --from-text <fichier> | rules <sub> --policy P --quote \"phrase\"")
        return 1
    try:
        rules.record(sub, args.policy, args.quote, owner)
    except ValueError as error:
        print(f"ERREUR {error}")
        return 1
    rules.save()
    print(f"r/{sub} ({owner or 'chauffe'}) : règle enregistrée, politique {args.policy}")
    return 0


def cmd_scan(args: argparse.Namespace, root: Path, fetch=reddit.http_get, sleep=time.sleep, **_: object) -> int:
    projects, ledger, rules, p = _load(root)
    errors = validate_portfolio(projects)
    if errors:
        print("\n".join(f"ERREUR {e}" for e in errors))
        return 1
    selected = {args.project: projects[args.project]} if args.project else projects
    candidates: dict[str, list] = {}
    unread: dict[str, list[str]] = {}
    warnings: list[str] = []
    if args.from_feed:
        if not args.project:
            print("ERREUR --from-feed demande --project")
            return 1
        xml = Path(args.from_feed).read_text(encoding="utf-8")
        threads = [t for t in reddit.parse_thread_feed(xml) if t.sub.lower() in (s.lower() for s in selected[args.project].subs)]
        candidates[args.project] = reddit.score_threads(selected[args.project], threads)
    else:
        specs: list[tuple[str, str]] = []
        owner: dict[str, str] = {}
        for slug, project in selected.items():
            read = [s for s in project.subs if rules.is_read(s)]
            skipped = [s for s in project.subs if not rules.is_read(s)]
            if skipped:
                unread[slug] = skipped
            for sub in read:
                specs.append((sub, reddit.build_query(project)))
                owner[sub.lower()] = slug
        threads, warnings = reddit.fetch_threads(specs, fetch, sleep)
        for slug, project in selected.items():
            mine = [t for t in threads if owner.get(t.sub.lower()) == slug]
            candidates[slug] = reddit.score_threads(project, mine)
    registry = Registry(p["comptes"])
    notes: list[str] = []
    proposals = plan(projects, candidates, ledger, rules, args.max, args.max_per_project, args.warmup, registry, args.date, notes)
    if not args.dry_run:
        record_proposals(proposals, ledger, args.date)
        ledger.save()
        cache = daypage.load_cache(p["fils"])
        for pr in proposals:
            daypage.remember(cache, pr.thread)
        daypage.save_cache(p["fils"], cache)
    p["sorties"].mkdir(parents=True, exist_ok=True)
    out = p["sorties"] / f"{args.date}.md"
    out.write_text(render_report(args.date, proposals, unread, ledger, p["reponses"], warnings + notes), encoding="utf-8")
    print(f"{len(proposals)} fil(s) retenu(s), rapport : {out}" + (" (essai à blanc : ledger inchangé)" if args.dry_run else ""))
    for w in warnings + notes:
        print(f"AVERTISSEMENT {w}")
    return 0


def cmd_check_reply(args: argparse.Namespace, root: Path, **_: object) -> int:
    projects, ledger, rules, p = _load(root)
    text = Path(args.file).read_text(encoding="utf-8")
    row = None
    if args.id:
        try:
            row = ledger.find(args.id)
        except KeyError as error:
            print(f"ERREUR {error}")
            return 1
        slug, sub = row.project, row.sub
        account = row.account
    else:
        if not (args.project and args.sub):
            print("ERREUR donner --id, ou --project et --sub")
            return 1
        slug, sub = args.project, args.sub
        account = args.account or ""
    project = projects[slug]
    snapshot = Ledger(p["ledger"])
    snapshot.rows = [r for r in snapshot.rows if not row or r.id != row.id]
    permitted, reason = link_allowed(snapshot, rules.policy(sub), args.warmup, account if Registry(p["comptes"]) else None,
                                     rules.flags(sub), args.date)
    others = {f.stem: f.read_text(encoding="utf-8") for f in p["reponses"].glob("*.md") if f.resolve() != Path(args.file).resolve()}
    errors, warnings = check_reply(text, project, permitted, others=others)
    for w in warnings:
        print(f"AVERTISSEMENT {w}")
    for e in errors:
        print(f"ERREUR {e}")
    has_link = bool(project_links_in(text, project))
    if row and not errors:
        row.has_link = has_link
        ledger.save()
    print(("FAIL" if errors else "PASS") + f" (lien dans la réponse : {'oui' if has_link else 'non'} ; lien permis : {'oui' if permitted else 'non, ' + reason})")
    return 1 if errors else 0


def cmd_mark(args: argparse.Namespace, root: Path, **_: object) -> int:
    _projects, ledger, _rules, _p = _load(root)
    try:
        row = ledger.find(args.id)
    except KeyError as error:
        print(f"ERREUR {error}")
        return 1
    row.status = args.status
    if args.link:
        row.has_link = args.link == "yes"
    ledger.save()
    print(f"{row.id} : {row.status}, lien {'oui' if row.has_link else 'non'}")
    return 0


def cmd_log(args: argparse.Namespace, root: Path, **_: object) -> int:
    projects, ledger, _rules, p = _load(root)
    registry = Registry(p["comptes"])
    account = getattr(args, "account", None) or ""
    if args.project not in projects:
        print(f"ERREUR projet inconnu : {args.project}")
        return 1
    if registry and not account:
        print("ERREUR des comptes sont enregistrés : préciser --account")
        return 1
    if account:
        try:
            account = registry.get(account).handle
        except (KeyError, AccountError) as error:
            print(f"ERREUR {error}")
            return 1
    owner = ledger.thread_owner(args.url)
    if owner and owner != args.project:
        print(f"ERREUR ce fil est déjà traité pour le projet {owner} : jamais deux projets dans le même fil")
        return 1
    sub = args.sub.removeprefix("r/")
    if account:
        why = ledger.conflict(account, sub, args.url, args.date)
        if why:
            print(f"ERREUR règle multi-comptes : {why}")
            return 1
    row = ledger.add(project=args.project, sub=sub, thread_url=args.url, kind=args.kind,
                     has_link=args.link == "yes", status="published", date=args.date, note=args.note or "",
                     account=account, origin=getattr(args, "origin", None) or "manual")
    ledger.save()
    print(f"{row.id} enregistrée")
    return 0


def cmd_ledger(args: argparse.Namespace, root: Path, **deps: object) -> int:
    """`ledger add --id cNNNN` : l'humain a publié, on l'inscrit. Sans --id : même effet que `log`."""
    if not args.id:
        return cmd_log(args, root, **deps)
    ok, info = daypage.mark_published(_paths(root)["ledger"], args.id)
    print(f"{info} : publié" if ok else f"ERREUR {info}")
    return 0 if ok else 1


def cmd_stats(args: argparse.Namespace, root: Path, **_: object) -> int:
    projects, ledger, _rules, _p = _load(root)
    with_link, total = ledger.ratio()
    print(f"global : {with_link} avec lien sur {total} comptée(s) ({(with_link / total if total else 0):.0%}, plafond 10 %)")
    for slug in projects:
        mine = [r for r in ledger.counted() if r.project == slug]
        print(f"- {slug} : {len(mine)} contribution(s), {sum(1 for r in mine if r.has_link)} avec lien, dernière : {ledger.last_contribution_date(slug) or 'jamais'}")
    registry = Registry(_p["comptes"])
    for handle, account in sorted(registry.accounts.items()):
        wl, tot = ledger.ratio(handle)
        ok_a, why_a = link_allowed(ledger, "declaree-ok", args.warmup, handle)
        print(f"- compte {handle} ({account.role or 'sans rôle'}, karma {account.karma}, {account.age_days(args.date)} j) : {wl} lien sur {tot}, "
              f"prochain lien {'possible' if ok_a else 'non'} ({why_a})")
    ok, reason = link_allowed(ledger, "declaree-ok", args.warmup)
    print(f"prochain lien possible : {'oui' if ok else 'non'} ({reason})")
    return 0


def cmd_send(args: argparse.Namespace, root: Path, **_: object) -> int:
    text = Path(args.file).read_text(encoding="utf-8")
    try:
        count = telegram.send(text, dry_run=args.dry_run)
    except telegram.TelegramConfigError as error:
        print(f"ERREUR {error}")
        return 1
    except Exception as error:  # le message d'une exception réseau ne doit jamais circuler
        print(f"ERREUR envoi Telegram impossible ({type(error).__name__})")
        return 1
    print(f"{count} message(s) {'à envoyer (essai à blanc)' if args.dry_run else 'envoyé(s)'}")
    return 0


def _csv(value: str | None) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def cmd_accounts(args: argparse.Namespace, root: Path, **_: object) -> int:
    projects, _ledger, _rules, p = _load(root)
    registry = Registry(p["comptes"])
    try:
        if args.action == "add":
            since = args.since
            if args.age_days is not None:
                since = (date.fromisoformat(args.date) - timedelta(days=args.age_days)).isoformat()
            registry.upsert(args.handle, role=args.role, karma=args.karma, since=since)
        elif args.action == "assign":
            registry.assign(args.handle, _csv(args.projects), _csv(args.subs), set(projects))
        elif args.action == "ban":
            if not args.sub:
                print("ERREUR accounts ban <pseudo> <communauté>")
                return 1
            registry.ban(args.handle, args.sub)
            print(f"r/{args.sub.removeprefix('r/')} fermée à tous les comptes : un bannissement ne se contourne pas avec un autre compte")
    except (AccountError, KeyError) as error:
        print(f"ERREUR {error}")
        return 1
    if args.action != "list":
        registry.save()
    for handle, a in sorted(registry.accounts.items()):
        print(f"u/{handle} : {a.role or 'sans rôle'}, karma {a.karma}, {a.age_days(args.date)} j, projets [{', '.join(a.projects)}], "
              f"communautés [{', '.join(a.subs)}]" + (f", bannis [{', '.join(a.bans)}]" if a.bans else ""))
    if not registry.accounts:
        print("aucun compte enregistré (mode mono-compte)")
    return 0


# --- chauffe ------------------------------------------------------------------------------------------------------------

def _all_drafts(p: dict[str, Path], day: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in p["reponses"].glob("*.md"):
        out[f"reponses/{f.name}"] = f.read_text(encoding="utf-8")
    folder = p["chauffe"] / day
    for f in folder.glob("*.md") if folder.is_dir() else []:
        out[f"chauffe/{f.name}"] = f.read_text(encoding="utf-8")
    return out


def _thread_of(row, cache: dict) -> "reddit.Thread | None":
    meta = cache.get(row.thread_url)
    if not meta:
        return None
    return reddit.Thread(daypage.thread_id(row.thread_url), row.sub, meta["title"], row.thread_url, meta.get("text", ""), meta.get("author", ""))


def _check_warmup_files(p: dict, projects: dict, registry: Registry, ledger: Ledger, day: str, per_sub: int,
                        cache: dict) -> tuple[dict[str, str], int]:
    """Contrôle chaque brouillon de chauffe du jour. Retourne ({id: problème}, nombre de PASS)."""
    problems: dict[str, str] = {}
    passed = 0
    banned = warmup.forbidden_terms(projects)
    drafts = _all_drafts(p, day)
    for row in ledger.rows:
        if row.date != day or row.origin != "warmup" or row.status == "skipped":
            continue
        path = p["chauffe"] / day / f"{row.account}__{daypage.thread_id(row.thread_url)}.md"
        if not path.exists():
            continue
        others = {k: v for k, v in drafts.items() if k != f"chauffe/{path.name}"}
        errors, _w = warmup.check_draft(path.read_text(encoding="utf-8"), _thread_of(row, cache), banned, others,
                                        registry.handles() - {row.account.lower()})
        same_sub = [r for r in ledger.rows if r.account == row.account and r.date == day and r.origin == "warmup"
                    and r.sub.lower() == row.sub.lower() and r.status != "skipped"]
        if len(same_sub) > per_sub:
            errors.append(f"plus de {per_sub} brouillons dans r/{row.sub} aujourd'hui pour ce compte")
        if errors:
            problems[row.id] = "contrôle refusé : " + " ; ".join(errors)
        else:
            passed += 1
    return problems, passed


def cmd_warmup(args: argparse.Namespace, root: Path, fetch=reddit.http_get, sleep=time.sleep, drafter=warmup.run_drafter, **_: object) -> int:
    projects, ledger, rules, p = _load(root)
    registry = Registry(p["comptes"])
    cache = daypage.load_cache(p["fils"])
    if args.action == "check":
        problems, passed = _check_warmup_files(p, projects, registry, ledger, args.date, args.per_sub, cache)
        for ident, text in sorted(problems.items()):
            print(f"FAIL {ident} : {text}")
        print(f"{passed} brouillon(s) PASS, {len(problems)} FAIL")
        return 1 if problems else 0
    return _warmup_run(args, projects, ledger, rules, registry, p, cache, fetch, sleep, drafter)


def _warmup_run(args, projects, ledger, rules, registry, p, cache, fetch, sleep, drafter, done_marker: Path | None = None) -> int:
    if not registry:
        print("ERREUR aucun compte enregistré : `promo.py accounts add ...` d'abord")
        return 1
    day = args.date
    needy = {h for h in registry.accounts
             if len([r for r in ledger.rows if r.account == h and r.date == day and r.origin == "warmup" and r.status != "skipped"]) < args.per_account}
    threads: list = []
    warnings: list[str] = []
    if getattr(args, "from_feed", None):
        threads = reddit.parse_thread_feed(Path(args.from_feed).read_text(encoding="utf-8"))
    elif needy:
        only = Registry(p["comptes"])
        only.accounts = {h: a for h, a in registry.accounts.items() if h in needy}
        subs = warmup.warmup_subs(only, projects, rules)
        if not subs:
            warnings.append("aucune communauté lue (règles) pour les comptes : `promo.py rules fetch|import <sub>` d'abord")
        else:
            threads, more = reddit.fetch_new_threads(subs, fetch, sleep)
            warnings += more
    items, notes = warmup.select_warmup(threads, registry, projects, ledger, rules, day, args.per_account, args.per_sub)
    ledger.save()
    for item in items:
        daypage.remember(cache, item.thread)
    daypage.save_cache(p["fils"], cache)
    drafter_cmd = getattr(args, "drafter", None)
    if drafter_cmd:
        for row in ledger.rows:
            if row.date != day or row.origin != "warmup" or row.status == "skipped":
                continue
            path = p["chauffe"] / day / f"{row.account}__{daypage.thread_id(row.thread_url)}.md"
            thread = _thread_of(row, cache)
            if path.exists() or thread is None:
                continue
            kind = row.note.split(" ", 1)[-1]
            text = drafter(drafter_cmd, warmup.brief_for(warmup.WarmupItem(row.account, thread, kind, row.id)))
            if not text:
                notes.append(f"{row.id} : rédacteur externe sans réponse")
                continue
            errors, _w = warmup.check_draft(text, thread, warmup.forbidden_terms(projects), _all_drafts(p, day),
                                            registry.handles() - {row.account.lower()})
            if errors:
                notes.append(f"{row.id} : brouillon du rédacteur refusé ({'; '.join(errors)})")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text.strip() + "\n", encoding="utf-8")
    problems, passed = _check_warmup_files(p, projects, registry, ledger, day, args.per_sub, cache)
    for ident, text in problems.items():
        notes.append(f"{ident} : {text}")
    total = len([r for r in ledger.rows if r.date == day and r.origin == "warmup" and r.status != "skipped"])
    print(f"chauffe : {len(items)} nouveau(x) fil(s), {total} au total aujourd'hui, {passed} brouillon(s) valide(s)")
    for w in warnings + notes:
        print(f"AVERTISSEMENT {w}")
    if done_marker is not None and not warnings:
        done_marker.write_text("ok", encoding="utf-8")
    return 0


# --- page du jour, serveur, daily ---------------------------------------------------------------------------------------

SCRIPT = Path(__file__).resolve()


def _page_html(root: Path, day: str, token: str | None = None) -> str:
    projects, ledger, _rules, p = _load(root)
    registry = Registry(p["comptes"])
    cache = daypage.load_cache(p["fils"])
    entries = daypage.build_entries(root, day, ledger, cache)
    problems, _ = _check_warmup_files(p, projects, registry, ledger, day, warmup.DEFAULT_PER_SUB, cache)
    for e in entries:
        if e.id in problems:
            e.draft = None
            e.problem = problems[e.id]
    return daypage.render_page(day, entries, registry, ledger, root, SCRIPT, data_dir(), token)


def cmd_page(args: argparse.Namespace, root: Path, **_: object) -> int:
    p = _paths(root)
    p["sorties"].mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else p["sorties"] / f"{args.date}.html"
    out.write_text(_page_html(root, args.date), encoding="utf-8")
    print(f"page du jour : {out.resolve()}")
    return 0


def cmd_serve(args: argparse.Namespace, root: Path, ready=None, **_: object) -> int:
    server = daypage.make_server(root, args.date, SCRIPT, args.port, data_dir(), builder=lambda token: _page_html(root, args.date, token))
    host, port = server.server_address[:2]
    print(f"serveur local http://{host}:{port}/ (127.0.0.1 seulement, Ctrl+C pour arrêter). Il n'écrit nulle part sur Reddit.")
    if ready:
        ready(server)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _check_promo_replies(p, projects, rules, ledger, day, warmup_n) -> None:
    """Contrôle les réponses de promo déposées pour les propositions du jour ; un FAIL est signalé, jamais forcé."""
    for row in ledger.rows:
        if row.date != day or row.origin != "promo" or row.status == "skipped":
            continue
        path = p["reponses"] / f"{daypage.thread_id(row.thread_url)}.md"
        if not path.exists():
            continue
        snapshot = Ledger(p["ledger"])
        snapshot.rows = [r for r in snapshot.rows if r.id != row.id]
        permitted, _ = link_allowed(snapshot, rules.policy(row.sub), warmup_n, row.account or None, rules.flags(row.sub), day)
        others = {f.stem: f.read_text(encoding="utf-8") for f in p["reponses"].glob("*.md") if f != path}
        text = path.read_text(encoding="utf-8")
        errors, _w = check_reply(text, projects[row.project], permitted, others=others)
        if errors:
            print(f"AVERTISSEMENT {row.id} : réponse de promo refusée par le contrôle ({'; '.join(errors)})")
        else:
            row.has_link = bool(project_links_in(text, projects[row.project]))
    ledger.save()


def cmd_daily(args: argparse.Namespace, root: Path, fetch=reddit.http_get, sleep=time.sleep, drafter=warmup.run_drafter, post=None, **_: object) -> int:
    """scan, chauffe, réponses de promo éligibles, page du jour. Idempotent : relancé le même jour, rien ne se duplique."""
    projects, _ledger, _rules, p = _load(root)
    errors = validate_portfolio(projects)
    if errors:
        print("\n".join(f"ERREUR {e}" for e in errors))
        return 1
    registry = Registry(p["comptes"])
    p["sorties"].mkdir(parents=True, exist_ok=True)
    scan_done = p["sorties"] / f".{args.date}.scan.ok"
    warm_done = p["sorties"] / f".{args.date}.chauffe.ok"
    if args.force:
        scan_done.unlink(missing_ok=True)
        warm_done.unlink(missing_ok=True)
    if args.no_scan:
        print("1/4 repérage : ignoré (--no-scan)")
    elif scan_done.exists():
        print("1/4 repérage : déjà fait aujourd'hui")
    else:
        print("1/4 repérage")
        scan_args = argparse.Namespace(project=None, from_feed=None, max=args.max, max_per_project=args.max_per_project, dry_run=False,
                                       warmup=args.warmup, date=args.date)
        cmd_scan(scan_args, root, fetch=fetch, sleep=sleep)
        scan_done.write_text("ok", encoding="utf-8")
    projects, ledger, rules, p = _load(root)
    if args.no_warmup or not registry:
        print("2/4 chauffe : ignorée" + (" (aucun compte enregistré)" if not registry else " (--no-warmup)"))
    else:
        print("2/4 chauffe" + (" (déjà faite, brouillons revérifiés)" if warm_done.exists() else ""))
        args.from_feed = None
        _warmup_run(args, projects, ledger, rules, registry, p, daypage.load_cache(p["fils"]), fetch, sleep, drafter,
                    None if warm_done.exists() else warm_done)
    projects, ledger, rules, p = _load(root)
    print("3/4 réponses de promo")
    _check_promo_replies(p, projects, rules, ledger, args.date, args.warmup)
    print("4/4 page du jour")
    cmd_page(argparse.Namespace(out=None, date=args.date), root)
    if args.telegram:
        ledger = Ledger(p["ledger"])
        today = [r for r in ledger.rows if r.date == args.date and r.origin in ("promo", "warmup") and r.status != "skipped"]
        lines = [f"Promo du {args.date} : {len(today)} brouillon(s) à relire et publier toi-même."]
        for handle in sorted({r.account for r in today}):
            lines.append(f"- {handle or 'compte'} : {sum(1 for r in today if r.account == handle)}")
        lines.append(f"Page : {(p['sorties'] / (args.date + '.html')).resolve()}")
        try:
            kwargs = {"post": post} if post else {}
            telegram.send("\n".join(lines), dry_run=args.dry_run_telegram, **kwargs)
            print("résumé Telegram " + ("prêt (essai à blanc)" if args.dry_run_telegram else "envoyé"))
        except telegram.TelegramConfigError as error:
            print(f"AVERTISSEMENT Telegram non configuré : {error}")
        except Exception as error:  # jamais de message réseau dans les journaux
            print(f"AVERTISSEMENT envoi Telegram impossible ({type(error).__name__})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="promo.py", description=__doc__)
    parser.add_argument("--data-dir", help="dossier de données (défaut : PROMO_DATA_DIR ou ~/.promo-projets)")
    parser.add_argument("--date", default=date.today().isoformat(), help="date du jour AAAA-MM-JJ (tests)")
    parser.add_argument("--warmup", type=int, default=WARMUP_DEFAULT, help="contributions sans lien avant le premier lien (par compte)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="crée le dossier de données").set_defaults(func=cmd_init)
    sub.add_parser("check", help="valide les fiches et le portefeuille").set_defaults(func=cmd_check)
    d = sub.add_parser("discover", help="découvre les communautés d'un projet")
    d.add_argument("project")
    d.set_defaults(func=cmd_discover)
    r = sub.add_parser("rules", help="règles d'une communauté : fetch <sub> | import <sub> --from-text F | <sub> --policy P --quote Q")
    r.add_argument("words", nargs="+", metavar="[fetch|import] sub")
    r.add_argument("--policy", choices=[x for x in POLICIES if x != "non-verifie"])
    r.add_argument("--quote", help="phrase de la règle, citée telle quelle")
    r.add_argument("--from-text", help="fichier texte des règles, extrait du navigateur (rules import)")
    r.set_defaults(func=cmd_rules)
    ac = sub.add_parser("accounts", help="registre des comptes Reddit (add, assign, ban, list)")
    ac.add_argument("action", choices=["add", "assign", "ban", "list"])
    ac.add_argument("handle", nargs="?", default="")
    ac.add_argument("sub", nargs="?", help="communauté (ban)")
    ac.add_argument("--role")
    ac.add_argument("--karma", type=int)
    ac.add_argument("--since", help="date de création du compte AAAA-MM-JJ")
    ac.add_argument("--age-days", type=int, help="âge du compte en jours (remplace --since)")
    ac.add_argument("--projects", help="slugs séparés par des virgules")
    ac.add_argument("--subs", help="communautés séparées par des virgules")
    ac.set_defaults(func=cmd_accounts)
    s = sub.add_parser("scan", help="repère les fils et écrit le rapport du jour")
    s.add_argument("--project")
    s.add_argument("--from-feed", help="fichier Atom déjà téléchargé (au lieu du réseau)")
    s.add_argument("--max", type=int, default=4)
    s.add_argument("--max-per-project", type=int, default=2)
    s.add_argument("--dry-run", action="store_true", help="n'enregistre rien dans le ledger")
    s.set_defaults(func=cmd_scan)
    w = sub.add_parser("warmup", help="chauffe : fils du jour par compte (run) ou contrôle des brouillons (check)")
    w.add_argument("action", choices=["run", "check"])
    w.add_argument("--per-account", type=int, default=warmup.DEFAULT_PER_ACCOUNT, help="fils par compte et par jour (3 à 5 conseillé)")
    w.add_argument("--per-sub", type=int, default=warmup.DEFAULT_PER_SUB, help="brouillons max par communauté, compte et jour")
    w.add_argument("--from-feed", help="fichier Atom déjà téléchargé (au lieu du réseau)")
    w.add_argument("--drafter", help="commande externe optionnelle qui rédige (brief JSON sur stdin, brouillon sur stdout)")
    w.set_defaults(func=cmd_warmup)
    c = sub.add_parser("check-reply", help="contrôles mécaniques d'une réponse")
    c.add_argument("file")
    c.add_argument("--id")
    c.add_argument("--project")
    c.add_argument("--sub")
    c.add_argument("--account")
    c.set_defaults(func=cmd_check_reply)
    m = sub.add_parser("mark", help="passe une contribution à published ou skipped")
    m.add_argument("id")
    m.add_argument("status", choices=["published", "skipped", "proposed"])
    m.add_argument("--link", choices=["yes", "no"])
    m.set_defaults(func=cmd_mark)
    for name, func, text in (("log", cmd_log, "enregistre une contribution déjà publiée (participation sans lien comprise)"),
                             ("ledger", cmd_ledger, "ledger add --id cNNNN : inscrit comme publiée une proposition que tu as publiée à la main")):
        lg = sub.add_parser(name, help=text)
        if name == "ledger":
            lg.add_argument("verb", choices=["add"])
            lg.add_argument("--id", help="proposition du jour à marquer publiée")
        lg.add_argument("--project", required=name == "log")
        lg.add_argument("--sub", required=name == "log")
        lg.add_argument("--url", required=name == "log")
        lg.add_argument("--account")
        lg.add_argument("--origin", choices=["promo", "warmup", "manual"])
        lg.add_argument("--kind", choices=["comment", "post"], default="comment")
        lg.add_argument("--link", choices=["yes", "no"], default="no")
        lg.add_argument("--note")
        lg.set_defaults(func=func)
    sub.add_parser("stats", help="ratio de liens (global et par compte) et rotation").set_defaults(func=cmd_stats)
    pg = sub.add_parser("page", help="écrit la page HTML du jour (le dernier clic reste à l'humain)")
    pg.add_argument("--out")
    pg.set_defaults(func=cmd_page)
    sv = sub.add_parser("serve", help="sert la page du jour sur 127.0.0.1 ; « Marquer publié » enregistre au ledger")
    sv.add_argument("--port", type=int, default=8765)
    sv.set_defaults(func=cmd_serve)
    dl = sub.add_parser("daily", help="scan, chauffe, réponses de promo, page du jour (idempotent, pour une tâche planifiée)")
    dl.add_argument("--max", type=int, default=4)
    dl.add_argument("--max-per-project", type=int, default=2)
    dl.add_argument("--per-account", type=int, default=warmup.DEFAULT_PER_ACCOUNT)
    dl.add_argument("--per-sub", type=int, default=warmup.DEFAULT_PER_SUB)
    dl.add_argument("--drafter", help="commande externe optionnelle qui rédige les brouillons de chauffe")
    dl.add_argument("--no-scan", action="store_true")
    dl.add_argument("--no-warmup", action="store_true")
    dl.add_argument("--force", action="store_true", help="refait le repérage et la chauffe même si déjà faits aujourd'hui")
    dl.add_argument("--telegram", action="store_true", help="envoie un court résumé Telegram (variables d'environnement)")
    dl.add_argument("--dry-run-telegram", action="store_true")
    dl.set_defaults(func=cmd_daily)
    se = sub.add_parser("send", help="envoie un rapport sur Telegram (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")
    se.add_argument("file")
    se.add_argument("--dry-run", action="store_true")
    se.set_defaults(func=cmd_send)
    return parser


def main(argv: list[str] | None = None, **deps: object) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    root = Path(args.data_dir) if args.data_dir else data_dir()
    try:
        return args.func(args, root, **deps)
    except (ProjectError, KeyError) as error:
        print(f"ERREUR {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
