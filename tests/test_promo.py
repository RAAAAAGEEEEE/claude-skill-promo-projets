"""Tests de promo-projets. Lancer : python -m unittest discover -s tests -v (depuis la racine du skill)."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import promo  # noqa: E402
from promo_core import telegram  # noqa: E402
from promo_core.channels import reddit  # noqa: E402
from promo_core.checkreply import check_reply  # noqa: E402
from promo_core.miniyaml import MiniYamlError, parse_front_matter  # noqa: E402
from promo_core.project import Keyword, ProjectError, load_project, load_projects, validate_portfolio  # noqa: E402
from promo_core.relevance import score_thread  # noqa: E402
from promo_core.scan import plan  # noqa: E402
from promo_core.state import Ledger, Rules, link_allowed  # noqa: E402

EXAMPLES = ROOT / "examples" / "projets"


def atom(entries: list[tuple[str, str, str]]) -> str:
    body = "".join(
        f'<entry><title>{t}</title><link href="{u}"/><content type="html">{c}</content></entry>' for t, u, c in entries
    )
    return f'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'


def thread_xml(sub: str, ident: str, title: str, text: str = "") -> tuple[str, str, str]:
    return title, f"https://www.reddit.com/r/{sub}/comments/{ident}/slug/", f"&lt;p&gt;{text}&lt;/p&gt; [link] [comments]"


def run_cli(argv: list[str], **deps: object) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = promo.main(argv, **deps)
    return code, out.getvalue()


class MiniYamlTests(unittest.TestCase):
    def test_parses_scalars_and_lists(self):
        data, body = parse_front_matter("---\nnom: A\nn: 3\nok: true\nl:\n  - x\n  - y | 2\n---\ncorps")
        self.assertEqual(data, {"nom": "A", "n": 3, "ok": True, "l": ["x", "y | 2"]})
        self.assertEqual(body, "corps")

    def test_rejects_missing_header_and_duplicates(self):
        with self.assertRaises(MiniYamlError):
            parse_front_matter("pas d'en-tête")
        with self.assertRaises(MiniYamlError):
            parse_front_matter("---\na: 1\na: 2\n---\n")
        with self.assertRaises(MiniYamlError):
            parse_front_matter("---\na: 1\n")


class ProjectTests(unittest.TestCase):
    def test_examples_load(self):
        projects = load_projects(EXAMPLES)
        self.assertEqual(set(projects), {"atlas-des-phares", "brume-quest"})
        self.assertEqual(validate_portfolio(projects), [])

    def test_fact_without_source_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = (EXAMPLES / "brume-quest.md").read_text(encoding="utf-8").replace(" | https://example.org/brume-quest/jouer", "")
            path = Path(tmp) / "brume-quest.md"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ProjectError):
                load_project(path)

    def test_same_sub_for_two_projects_is_an_error(self):
        projects = load_projects(EXAMPLES)
        projects["brume-quest"].subs.append("Lighthouses")
        errors = validate_portfolio(projects)
        self.assertEqual(len(errors), 1)
        self.assertIn("Lighthouses", errors[0])

    def test_missing_required_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.md"
            path.write_text("---\nnom: X\n---\n", encoding="utf-8")
            with self.assertRaises(ProjectError):
                load_project(path)


class RelevanceTests(unittest.TestCase):
    kws = [Keyword("ai", 2, "word"), Keyword("robot", 2, "prefix"), Keyword("drone", 1, "prefix")]

    def test_whole_words_not_substrings(self):
        self.assertEqual(score_thread("he said so", "", self.kws).score, 0)
        self.assertEqual(score_thread("AI is here", "", self.kws).score, 2)

    def test_prefix_and_accents(self):
        self.assertEqual(score_thread("Mes robots", "", self.kws).score, 2)
        self.assertEqual(score_thread("Éléphant", "", [Keyword("elephant", 2, "word")]).score, 2)

    def test_excluded_word_zeroes_the_score(self):
        self.assertEqual(score_thread("robot giveaway", "", self.kws, ["giveaway"]).score, 0)

    def test_broken_regex_drops_only_that_keyword(self):
        kws = [Keyword("(", 5, "regex"), Keyword("robot", 2, "prefix")]
        self.assertEqual(score_thread("robot", "", kws).score, 2)


class RedditReadingTests(unittest.TestCase):
    def test_parse_thread_feed(self):
        xml = atom([thread_xml("Lighthouses", "abc12", "Un phare &amp; sa lentille", "Texte"), ("Pas un fil", "https://example.org/x", "")])
        threads = reddit.parse_thread_feed(xml)
        self.assertEqual(len(threads), 1)
        self.assertEqual((threads[0].id, threads[0].sub, threads[0].title, threads[0].text), ("abc12", "Lighthouses", "Un phare & sa lentille", "Texte"))

    def test_parse_garbage_feed(self):
        self.assertEqual(reddit.parse_thread_feed("pas du xml"), [])

    def test_fetch_threads_stops_at_429_and_keeps_what_was_read(self):
        calls: list[str] = []

        def fetch(url: str):
            calls.append(url)
            if len(calls) == 2:
                return 429, ""
            return 200, atom([thread_xml("A" + str(len(calls)), "id" + str(len(calls)), "t")])

        threads, warnings = reddit.fetch_threads([("Aa", "q"), ("Bb", "q"), ("Cc", "q")], fetch, lambda s: None)
        self.assertEqual(len(threads), 1)
        self.assertEqual(len(calls), 2)
        self.assertIn("429", warnings[0])

    def test_fetch_uses_search_rss_restricted_to_sub(self):
        seen: list[str] = []
        reddit.fetch_threads([("Lighthouses", 'phare OR "patrimoine maritime"')], lambda u: (seen.append(u) or (200, atom([]))), lambda s: None)
        self.assertIn("/r/Lighthouses/search.rss?q=", seen[0])
        self.assertIn("restrict_sr=1", seen[0])

    def test_discover_merges_and_skips_user_profiles(self):
        sub = lambda n: (n, f"https://www.reddit.com/r/{n}/", "desc [link]")  # noqa: E731
        pages = {0: atom([sub("Alpha"), sub("u_bob")]), 1: atom([sub("alpha"), sub("Beta")])}
        counter = iter([0, 1])
        found, _ = reddit.discover(["a", "b"], lambda u: (200, pages[next(counter)]), lambda s: None)
        self.assertEqual([(s.name, s.mentions) for s in found], [("Alpha", 2), ("Beta", 1)])

    def test_promo_rule_detection(self):
        self.assertEqual(reddit.find_promo_rule("Be nice. No self-promotion or advertising.")[0], "forbidden")
        self.assertEqual(reddit.find_promo_rule("Self promotion allowed on Fridays.")[0], "mentioned")
        self.assertEqual(reddit.find_promo_rule("Welcome to the sub.")[0], "unknown")

    def test_measure_excludes_and_ranks(self):
        project = load_projects(EXAMPLES)["atlas-des-phares"]
        day = 86400.0
        now = 100 * day
        threads = [("Un phare breton", "", now - i * day / 4) for i in range(40)]
        stats = reddit.ArchiveStats(50_000, False, threads, "No self-promotion.", now - 10 * day)
        m = reddit.measure(project, reddit.SubCandidate("Lighthouses", "", ""), stats, now)
        self.assertIsNone(m.excluded)
        self.assertEqual(m.promo_verdict, "forbidden")
        self.assertGreater(m.rank, 70)
        small = reddit.ArchiveStats(100, False, threads, "", None)
        self.assertIn("500", reddit.measure(project, reddit.SubCandidate("x", "", ""), small, now).excluded or "")
        dead = reddit.ArchiveStats(50_000, False, [("phare", "", now - 60 * day)] * 5, "", None)
        self.assertIn("30 jours", reddit.measure(project, reddit.SubCandidate("x", "", ""), dead, now).excluded or "")
        adult = reddit.ArchiveStats(50_000, True, threads, "", None)
        self.assertEqual(reddit.measure(project, reddit.SubCandidate("x", "", ""), adult, now).excluded, "contenu adulte")
        self.assertIn("illisible", reddit.measure(project, reddit.SubCandidate("x", "", ""), None, now).excluded or "")

    def test_parse_archive_reads_subscribers_and_sidebar(self):
        posts = {"data": [{"title": "t", "created_utc": 10, "selftext": "s", "subreddit_subscribers": 1234}, {"bad": 1}]}
        record = {"data": [{"public_description": "pd", "description": "d", "retrieved_on": 5, "over18": False}]}
        stats = reddit.parse_archive(posts, record)
        self.assertEqual((stats.subscribers, len(stats.threads), stats.sidebar), (1234, 1, "pd\nd"))

    def test_rank_score_bounds(self):
        self.assertEqual(reddit.rank_score(0, 0, None), 0)
        self.assertEqual(reddit.rank_score(1, 10, 10_000_000), 100)


class LedgerTests(unittest.TestCase):
    def ledger(self, rows: list[tuple[str, bool, str]]) -> Ledger:
        led = Ledger(Path(tempfile.mkdtemp()) / "l.csv")
        for i, (project, link, status) in enumerate(rows):
            led.add(project=project, sub="S", thread_url=f"u{i}", kind="comment", has_link=link, status=status)
        return led

    def test_policy_blocks_link(self):
        led = self.ledger([("a", False, "published")] * 40)
        self.assertFalse(link_allowed(led, "interdit")[0])
        self.assertFalse(link_allowed(led, "non-verifie")[0])
        self.assertFalse(link_allowed(led, "fil-dedie")[0])
        self.assertTrue(link_allowed(led, "declaree-ok")[0])

    def test_warmup_required(self):
        led = self.ledger([("a", False, "published")] * 5)
        ok, reason = link_allowed(led, "declaree-ok", warmup=30)
        self.assertFalse(ok)
        self.assertIn("5/30", reason)

    def test_one_in_ten_across_projects(self):
        rows = [("a", False, "published")] * 12 + [("b", True, "published")] + [("a", False, "published")] * 3
        led = self.ledger(rows)
        self.assertFalse(link_allowed(led, "declaree-ok", warmup=5)[0])  # lien de b dans les 9 dernières, projet différent
        led2 = self.ledger(rows[:12] + [("b", True, "published")] + [("a", False, "published")] * 9)
        self.assertTrue(link_allowed(led2, "declaree-ok", warmup=5)[0])

    def test_skipped_do_not_count_but_proposed_do(self):
        led = self.ledger([("a", False, "published")] * 10 + [("a", True, "skipped")])
        self.assertTrue(link_allowed(led, "declaree-ok", warmup=5)[0])
        led.add(project="a", sub="S", thread_url="z", kind="comment", has_link=True, status="proposed")
        self.assertFalse(link_allowed(led, "declaree-ok", warmup=5)[0])

    def test_csv_roundtrip(self):
        led = self.ledger([("a", True, "published")])
        led.save()
        again = Ledger(led.path)
        self.assertEqual((again.rows[0].has_link, again.rows[0].project), (True, "a"))

    def test_rules_need_quote_and_valid_policy(self):
        rules = Rules(Path(tempfile.mkdtemp()) / "r.json")
        with self.assertRaises(ValueError):
            rules.record("S", "declaree-ok", "  ")
        with self.assertRaises(ValueError):
            rules.record("S", "non-verifie", "x")
        self.assertEqual(rules.policy("S"), "non-verifie")
        rules.record("S", "interdit", "No ads.")
        self.assertEqual((rules.policy("s"), rules.is_read("S")), ("interdit", True))


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.projects = load_projects(EXAMPLES)
        self.ledger = Ledger(Path(tempfile.mkdtemp()) / "l.csv")
        self.rules = Rules(Path(tempfile.mkdtemp()) / "r.json")
        for sub in ("Lighthouses", "IndieGaming"):
            self.rules.record(sub, "declaree-ok", "Self-promo ok if disclosed.")

    def cand(self, sub: str, ident: str):
        return (reddit.Thread(ident, sub, "t", f"https://www.reddit.com/r/{sub}/comments/{ident}/s/", ""), 4, ["k"])

    def test_rotation_alternates_projects_and_caps_per_project(self):
        cands = {
            "atlas-des-phares": [self.cand("Lighthouses", "a1"), self.cand("Lighthouses", "a2"), self.cand("Lighthouses", "a3")],
            "brume-quest": [self.cand("IndieGaming", "b1"), self.cand("IndieGaming", "b2")],
        }
        props = plan(self.projects, cands, self.ledger, self.rules, max_total=4, max_per_project=2, warmup=0)
        self.assertEqual([p.project.slug for p in props], ["atlas-des-phares", "brume-quest", "atlas-des-phares", "brume-quest"])

    def test_least_recent_project_goes_first(self):
        self.ledger.add(project="atlas-des-phares", sub="S", thread_url="old", kind="comment", has_link=False, status="published", date="2026-10-01")
        cands = {"atlas-des-phares": [self.cand("Lighthouses", "a1")], "brume-quest": [self.cand("IndieGaming", "b1")]}
        props = plan(self.projects, cands, self.ledger, self.rules, warmup=0)
        self.assertEqual(props[0].project.slug, "brume-quest")

    def test_same_thread_never_given_to_two_projects(self):
        shared = self.cand("Lighthouses", "x1")
        props = plan(self.projects, {"atlas-des-phares": [shared], "brume-quest": [shared]}, self.ledger, self.rules, warmup=0)
        self.assertEqual(len(props), 1)

    def test_known_threads_are_skipped(self):
        shared = self.cand("Lighthouses", "x1")
        self.ledger.add(project="brume-quest", sub="S", thread_url=shared[0].url, kind="comment", has_link=False, status="published")
        self.assertEqual(plan(self.projects, {"atlas-des-phares": [shared]}, self.ledger, self.rules, warmup=0), [])

    def test_one_link_per_pass_and_policy_respected(self):
        cands = {
            "atlas-des-phares": [self.cand("Lighthouses", "a1")],
            "brume-quest": [self.cand("IndieGaming", "b1")],
        }
        props = plan(self.projects, cands, self.ledger, self.rules, warmup=0)
        self.assertEqual([p.link_ok for p in props], [True, False])
        self.assertIn("un seul lien", props[1].link_reason)
        self.rules.record("Lighthouses", "interdit", "No promo.")
        props = plan(self.projects, cands, self.ledger, self.rules, warmup=0)
        self.assertFalse(props[0].link_ok)


class CheckReplyTests(unittest.TestCase):
    project = load_projects(EXAMPLES)["atlas-des-phares"]

    def check(self, text: str, permitted: bool = True, others: dict | None = None):
        return check_reply(text, self.project, permitted, others=others)

    def test_clean_reply_without_link_passes(self):
        self.assertEqual(self.check("Le phare de Ouessant date de 1695, regarde aussi le registre local.", False)[0], [])

    def test_dashes_refused(self):
        self.assertTrue(any("tiret" in e for e in self.check("Bonne idée — merci")[0]))

    def test_link_needs_mention_and_permission(self):
        link = "https://example.org/atlas-des-phares/ouessant"
        errors, _ = self.check(f"Voir {link}")
        self.assertTrue(any("mention" in e for e in errors))
        errors, _ = self.check(f"Je tiens Atlas des Phares, voir {link}")
        self.assertEqual(errors, [])
        errors, _ = self.check(f"Je tiens Atlas des Phares, voir {link}", permitted=False)
        self.assertTrue(any("plafond" in e for e in errors))

    def test_foreign_url_refused(self):
        self.assertTrue(any("absente de la fiche" in e for e in self.check("regarde https://autre.example.net/page")[0]))

    def test_too_long_and_empty(self):
        self.assertTrue(any("trop longue" in e for e in self.check("a" * 1500)[0]))
        self.assertEqual(self.check("   ")[0], ["réponse vide"])

    def test_near_duplicate_refused(self):
        text = "Voici une réponse précise sur la lentille de Fresnel et son histoire."
        self.assertTrue(any("quasi identique" in e for e in self.check(text, False, {"old": text + "!"})[0]))

    def test_unsourced_number_is_a_warning(self):
        errors, warnings = self.check("Il y a 4242 phares.", False)
        self.assertEqual(errors, [])
        self.assertTrue(any("4242" in w for w in warnings))


class TelegramTests(unittest.TestCase):
    def test_chunks_respect_size(self):
        parts = telegram.chunks("ligne\n" * 2000, 3800)
        self.assertTrue(all(len(p) <= 3800 for p in parts))
        self.assertEqual("".join(parts), "ligne\n" * 2000)

    def test_missing_env_raises(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(telegram.TelegramConfigError):
                telegram.send("x")

    def test_send_posts_each_chunk_and_dry_run_does_not(self):
        calls: list[tuple[str, dict]] = []
        env = {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "42"}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(telegram.send("a\n" * 5000, dry_run=True, post=lambda u, p: calls.append((u, p)) or 200), 3)
            self.assertEqual(calls, [])
            self.assertEqual(telegram.send("a\n" * 5000, post=lambda u, p: calls.append((u, p)) or 200), 3)
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[0][1]["chat_id"], "42")


class CliEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.base = ["--data-dir", self.tmp, "--date", "2026-10-08", "--warmup", "0"]
        run_cli(self.base + ["init"])

    def cli(self, *argv: str, **deps: object):
        return run_cli(self.base + list(argv), **deps)

    def test_init_check_and_unread_rules_are_nv(self):
        code, out = self.cli("check")
        self.assertEqual(code, 0)
        self.assertIn("[NV]", out)

    def test_rules_requires_membership_and_quote(self):
        self.assertEqual(self.cli("rules", "Inconnu", "--policy", "interdit", "--quote", "x")[0], 1)
        self.assertEqual(self.cli("rules", "Lighthouses", "--policy", "interdit", "--quote", " ")[0], 1)
        self.assertEqual(self.cli("rules", "Lighthouses", "--policy", "declaree-ok", "--quote", "Disclosed promo ok.")[0], 0)
        data = json.loads((Path(self.tmp) / "communautes.json").read_text(encoding="utf-8"))
        self.assertEqual(data["lighthouses"]["project"], "atlas-des-phares")

    def test_scan_skips_unread_subs_then_proposes_after_reading(self):
        calls: list[str] = []

        def fetch(url: str):
            calls.append(url)
            return 200, atom([thread_xml("Lighthouses", "t1", "Quel phare visiter en Bretagne ?", "Je cherche un phare")])

        code, out = self.cli("scan", fetch=fetch, sleep=lambda s: None)
        self.assertEqual(calls, [])  # règle non lue : aucun accès réseau
        report = (Path(self.tmp) / "sorties" / "2026-10-08.md").read_text(encoding="utf-8")
        self.assertIn("[NV]", report)
        self.cli("rules", "Lighthouses", "--policy", "declaree-ok", "--quote", "Disclosed promo ok.")
        code, out = self.cli("scan", fetch=fetch, sleep=lambda s: None)
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        report = (Path(self.tmp) / "sorties" / "2026-10-08.md").read_text(encoding="utf-8")
        self.assertIn("https://www.reddit.com/r/Lighthouses/comments/t1/", report)
        self.assertIn("AUTORISÉ", report)
        self.assertIn("c0001", report)
        # relancer le même jour ne reproposer pas le même fil
        self.cli("scan", fetch=fetch, sleep=lambda s: None)
        report = (Path(self.tmp) / "sorties" / "2026-10-08.md").read_text(encoding="utf-8")
        self.assertIn("Aucun fil retenu", report)

    def test_check_reply_updates_ledger_and_mark(self):
        self.cli("rules", "Lighthouses", "--policy", "declaree-ok", "--quote", "Disclosed promo ok.")
        fetch = lambda u: (200, atom([thread_xml("Lighthouses", "t1", "Quel phare visiter ?")]))  # noqa: E731
        self.cli("scan", fetch=fetch, sleep=lambda s: None)
        reply = Path(self.tmp) / "reponses" / "t1.md"
        reply.write_text("Je tiens Atlas des Phares : https://example.org/atlas-des-phares/ouessant répond à ça.", encoding="utf-8")
        code, out = self.cli("check-reply", str(reply), "--id", "c0001")
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)
        self.assertEqual(Ledger(Path(self.tmp) / "ledger.csv").find("c0001").has_link, True)
        self.assertEqual(self.cli("mark", "c0001", "published")[0], 0)
        self.assertEqual(Ledger(Path(self.tmp) / "ledger.csv").find("c0001").status, "published")

    def test_check_reply_fails_when_policy_forbids_link(self):
        self.cli("rules", "Lighthouses", "--policy", "interdit", "--quote", "No promo.")
        reply = Path(self.tmp) / "r.md"
        reply.write_text("Je tiens Atlas des Phares : https://example.org/atlas-des-phares", encoding="utf-8")
        code, out = self.cli("check-reply", str(reply), "--project", "atlas-des-phares", "--sub", "Lighthouses")
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)

    def test_log_refuses_second_project_in_same_thread(self):
        url = "https://www.reddit.com/r/Lighthouses/comments/zz/s/"
        self.assertEqual(self.cli("log", "--project", "atlas-des-phares", "--sub", "Lighthouses", "--url", url)[0], 0)
        code, out = self.cli("log", "--project", "brume-quest", "--sub", "IndieGaming", "--url", url)
        self.assertEqual(code, 1)
        self.assertIn("deux projets", out)

    def test_stats_reports_ratio(self):
        self.cli("log", "--project", "atlas-des-phares", "--sub", "Lighthouses", "--url", "u1")
        self.cli("log", "--project", "brume-quest", "--sub", "IndieGaming", "--url", "u2", "--link", "yes")
        code, out = self.cli("stats")
        self.assertIn("1 avec lien sur 2", out)

    def test_dry_run_leaves_ledger_untouched(self):
        self.cli("rules", "Lighthouses", "--policy", "interdit", "--quote", "No promo.")
        fetch = lambda u: (200, atom([thread_xml("Lighthouses", "t9", "Un phare")]))  # noqa: E731
        self.cli("scan", "--dry-run", fetch=fetch, sleep=lambda s: None)
        self.assertEqual(Ledger(Path(self.tmp) / "ledger.csv").rows, [])

    def test_from_feed_file(self):
        feed = Path(self.tmp) / "feed.xml"
        feed.write_text(atom([thread_xml("Lighthouses", "f1", "Phare de Fresnel"), thread_xml("Autre", "f2", "Phare")]), encoding="utf-8")
        code, out = self.cli("scan", "--project", "atlas-des-phares", "--from-feed", str(feed))
        self.assertEqual(code, 0)
        self.assertIn("1 fil(s) retenu(s)", out)

    def test_discover_writes_report_with_nv(self):
        def fetch(url: str):
            if "subreddits/search.rss" in url:
                return 200, atom([("Lighthouses", "https://www.reddit.com/r/Lighthouses/", "x [link]")])
            if "posts/search" in url:
                now = 1_790_000_000
                return 200, json.dumps({"data": [{"title": "Un phare", "created_utc": now - i * 3600, "subreddit_subscribers": 9000} for i in range(30)]})
            return 200, json.dumps({"data": [{"description": "No self-promotion.", "retrieved_on": 1}]})

        code, out = self.cli("discover", "atlas-des-phares", fetch=fetch, sleep=lambda s: None)
        self.assertEqual(code, 0, out)
        report = (Path(self.tmp) / "sorties" / "decouverte-atlas-des-phares-2026-10-08.md").read_text(encoding="utf-8")
        self.assertIn("r/Lighthouses", report)
        self.assertIn("[NV]", report)

    def test_send_dry_run_without_env_fails_cleanly(self):
        report = Path(self.tmp) / "x.md"
        report.write_text("bonjour", encoding="utf-8")
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            code, out = self.cli("send", str(report), "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("TELEGRAM_BOT_TOKEN", out)


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
