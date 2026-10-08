#!/usr/bin/env python3
"""promo-projets : repérage Reddit multi-projets, ledger commun, contrôle des réponses. Rien n'est publié par l'outil."""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from promo_core import telegram  # noqa: E402
from promo_core.channels import reddit  # noqa: E402
from promo_core.checkreply import check_reply, project_links_in  # noqa: E402
from promo_core.project import ProjectError, load_projects, validate_portfolio  # noqa: E402
from promo_core.scan import plan, record_proposals, render_discovery, render_report  # noqa: E402
from promo_core.state import POLICIES, WARMUP_DEFAULT, Ledger, Rules, data_dir, link_allowed  # noqa: E402

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "projets"


def _paths(root: Path) -> dict[str, Path]:
    return {
        "projets": root / "projets", "ledger": root / "ledger.csv", "rules": root / "communautes.json",
        "sorties": root / "sorties", "reponses": root / "reponses",
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
    with_link, total = ledger.ratio()
    print(f"{len(projects)} projet(s), ledger : {with_link} lien(s) sur {total} contribution(s) comptée(s)")
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


def cmd_rules(args: argparse.Namespace, root: Path, **_: object) -> int:
    projects, _ledger, rules, p = _load(root)
    sub = args.sub.removeprefix("r/")
    owners = [s for s, pr in projects.items() if sub.lower() in (x.lower() for x in pr.subs)]
    if not owners:
        print(f"ERREUR r/{sub} ne figure dans aucune fiche projet : l'ajouter à `subs` d'un seul projet d'abord")
        return 1
    try:
        rules.record(sub, args.policy, args.quote, owners[0])
    except ValueError as error:
        print(f"ERREUR {error}")
        return 1
    rules.save()
    print(f"r/{sub} ({owners[0]}) : règle enregistrée, politique {args.policy}")
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
    proposals = plan(projects, candidates, ledger, rules, args.max, args.max_per_project, args.warmup)
    if not args.dry_run:
        record_proposals(proposals, ledger, args.date)
        ledger.save()
    p["sorties"].mkdir(parents=True, exist_ok=True)
    out = p["sorties"] / f"{args.date}.md"
    out.write_text(render_report(args.date, proposals, unread, ledger, p["reponses"], warnings), encoding="utf-8")
    print(f"{len(proposals)} fil(s) retenu(s), rapport : {out}" + (" (essai à blanc : ledger inchangé)" if args.dry_run else ""))
    for w in warnings:
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
    else:
        if not (args.project and args.sub):
            print("ERREUR donner --id, ou --project et --sub")
            return 1
        slug, sub = args.project, args.sub
    project = projects[slug]
    snapshot = Ledger(p["ledger"])
    snapshot.rows = [r for r in snapshot.rows if not row or r.id != row.id]
    permitted, reason = link_allowed(snapshot, rules.policy(sub), args.warmup)
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
    projects, ledger, _rules, _p = _load(root)
    if args.project not in projects:
        print(f"ERREUR projet inconnu : {args.project}")
        return 1
    owner = ledger.thread_owner(args.url)
    if owner and owner != args.project:
        print(f"ERREUR ce fil est déjà traité pour le projet {owner} : jamais deux projets dans le même fil")
        return 1
    row = ledger.add(project=args.project, sub=args.sub.removeprefix("r/"), thread_url=args.url, kind=args.kind,
                     has_link=args.link == "yes", status="published", date=args.date, note=args.note or "")
    ledger.save()
    print(f"{row.id} enregistrée")
    return 0


def cmd_stats(args: argparse.Namespace, root: Path, **_: object) -> int:
    projects, ledger, _rules, _p = _load(root)
    with_link, total = ledger.ratio()
    print(f"global : {with_link} avec lien sur {total} comptée(s) ({(with_link / total if total else 0):.0%}, plafond 10 %)")
    for slug in projects:
        mine = [r for r in ledger.counted() if r.project == slug]
        print(f"- {slug} : {len(mine)} contribution(s), {sum(1 for r in mine if r.has_link)} avec lien, dernière : {ledger.last_contribution_date(slug) or 'jamais'}")
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="promo.py", description=__doc__)
    parser.add_argument("--data-dir", help="dossier de données (défaut : PROMO_DATA_DIR ou ~/.promo-projets)")
    parser.add_argument("--date", default=date.today().isoformat(), help="date du jour AAAA-MM-JJ (tests)")
    parser.add_argument("--warmup", type=int, default=WARMUP_DEFAULT, help="contributions sans lien avant le premier lien")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="crée le dossier de données").set_defaults(func=cmd_init)
    sub.add_parser("check", help="valide les fiches et le portefeuille").set_defaults(func=cmd_check)
    d = sub.add_parser("discover", help="découvre les communautés d'un projet")
    d.add_argument("project")
    d.set_defaults(func=cmd_discover)
    r = sub.add_parser("rules", help="enregistre une règle d'autopromotion LUE sur l'onglet Règles")
    r.add_argument("sub")
    r.add_argument("--policy", required=True, choices=[x for x in POLICIES if x != "non-verifie"])
    r.add_argument("--quote", required=True, help="phrase de la règle, citée telle quelle")
    r.set_defaults(func=cmd_rules)
    s = sub.add_parser("scan", help="repère les fils et écrit le rapport du jour")
    s.add_argument("--project")
    s.add_argument("--from-feed", help="fichier Atom déjà téléchargé (au lieu du réseau)")
    s.add_argument("--max", type=int, default=4)
    s.add_argument("--max-per-project", type=int, default=2)
    s.add_argument("--dry-run", action="store_true", help="n'enregistre rien dans le ledger")
    s.set_defaults(func=cmd_scan)
    c = sub.add_parser("check-reply", help="contrôles mécaniques d'une réponse")
    c.add_argument("file")
    c.add_argument("--id")
    c.add_argument("--project")
    c.add_argument("--sub")
    c.set_defaults(func=cmd_check_reply)
    m = sub.add_parser("mark", help="passe une contribution à published ou skipped")
    m.add_argument("id")
    m.add_argument("status", choices=["published", "skipped", "proposed"])
    m.add_argument("--link", choices=["yes", "no"])
    m.set_defaults(func=cmd_mark)
    lg = sub.add_parser("log", help="enregistre une contribution déjà publiée (participation sans lien comprise)")
    lg.add_argument("--project", required=True)
    lg.add_argument("--sub", required=True)
    lg.add_argument("--url", required=True)
    lg.add_argument("--kind", choices=["comment", "post"], default="comment")
    lg.add_argument("--link", choices=["yes", "no"], default="no")
    lg.add_argument("--note")
    lg.set_defaults(func=cmd_log)
    sub.add_parser("stats", help="ratio de liens et rotation").set_defaults(func=cmd_stats)
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
