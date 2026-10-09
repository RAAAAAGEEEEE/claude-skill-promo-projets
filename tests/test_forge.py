"""Tests v0.2.0 : multi-comptes, chauffe, règles lues, page du jour, serveur local, daily. Réseau toujours simulé.

Lancer : python -m unittest discover -s tests -v (depuis la racine du skill). Pseudos fictifs uniquement.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import promo  # noqa: E402
from promo_core import daypage, warmup  # noqa: E402
from promo_core.accounts import AccountError, Registry, clean_handle  # noqa: E402
from promo_core.channels import reddit  # noqa: E402
from promo_core.project import load_projects  # noqa: E402
from promo_core.ruleflags import derive_policy, parse_flags  # noqa: E402
from promo_core.rulesfetch import fetch_rules, is_block_page  # noqa: E402
from promo_core.state import Ledger, Rules, link_allowed  # noqa: E402

EXAMPLES = ROOT / "examples" / "projets"
DAY = "2026-10-08"  # un jeudi
BLOCK_PAGE = "<!doctype html><html><head><title>Verification</title></head><body>Please wait for verification. Blocked by network security.</body></html>"
RULES_OK = "1. Be civil.\n2. Self-promotion is allowed if you disclose it. Follow the 9:1 rule: nine useful posts for each promotional one.\n3. Minimum 50 karma to comment."
RULES_NO = "Rule 1: No self-promotion or advertising of any kind. Links to your own site are not allowed."


def run_cli(argv, **deps):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = promo.main(argv, **deps)
    return code, out.getvalue()


def entry(sub, ident, title, text="", author=""):
    a = f"<author><name>/u/{author}</name></author>" if author else ""
    return (f'<entry><title>{title}</title><link href="https://www.reddit.com/r/{sub}/comments/{ident}/slug/"/>{a}'
            f'<content type="html">&lt;p&gt;{text}&lt;/p&gt; [link] [comments]</content></entry>')


def feed(*entries):
    return '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">' + "".join(entries) + "</feed>"


def thread(sub="Lighthouses", ident="t1", title="How do I photograph lighthouses at night with a phone?", text="", author=""):
    return reddit.Thread(ident, sub, title, f"https://www.reddit.com/r/{sub}/comments/{ident}/slug/", text, author)


GOOD = ("For night shots of lighthouses I rest the phone on a wall or a bag, use the night mode with a two second timer, "
        "and lower the exposure so the beam does not blow out the sky.")


class FlagTests(unittest.TestCase):
    def test_forbidden_and_links(self):
        f = parse_flags(RULES_NO)
        self.assertTrue(f["autopromo_interdite"])
        self.assertTrue(f["liens_interdits"])
        self.assertEqual(derive_policy(f), "interdit")

    def test_ratio_karma_and_policy(self):
        f = parse_flags(RULES_OK)
        self.assertFalse(f["autopromo_interdite"])
        self.assertEqual(f["ratio_fenetre"], 10)
        self.assertEqual(f["karma_min"], 50)
        self.assertEqual(derive_policy(f), "declaree-ok")

    def test_percent_ratio_and_age(self):
        f = parse_flags("Self-promotion: keep it under 10% of your activity. Accounts must be at least 30 days old.")
        self.assertEqual(f["ratio_fenetre"], 10)
        self.assertEqual(f["age_min_jours"], 30)
        f2 = parse_flags("Self promotion must stay under 5%.")
        self.assertEqual(f2["ratio_fenetre"], 20)

    def test_dedicated_day_english_and_french(self):
        f = parse_flags("No self-promotion except on Saturdays.")
        self.assertEqual(f["jour_autopromo"], 5)
        self.assertFalse(f["autopromo_interdite"])
        g = parse_flags("Autopromotion autorisée uniquement le dimanche.")
        self.assertEqual(g["jour_autopromo"], 6)
        self.assertEqual(derive_policy(g), "declaree-ok")

    def test_dedicated_thread(self):
        f = parse_flags("Self-promotion only in the weekly thread.")
        self.assertTrue(f["fil_dedie"])
        self.assertEqual(derive_policy(f), "fil-dedie")

    def test_french_forbidden_and_silence(self):
        self.assertTrue(parse_flags("Autopromotion interdite.")["autopromo_interdite"])
        silent = parse_flags("Soyez courtois. Pas d'insultes.")
        self.assertEqual(derive_policy(silent), "non-verifie")  # silence n'est pas une autorisation


class LinkRulesTests(unittest.TestCase):
    def ledger(self):
        led = Ledger(Path(tempfile.mkdtemp()) / "l.csv")
        for i in range(12):
            led.add(project="a", sub="S", thread_url=f"a{i}", kind="comment", has_link=False, status="published", account="compte_a")
        return led

    def test_ratio_is_per_account(self):
        led = self.ledger()
        led.add(project="a", sub="S", thread_url="x", kind="comment", has_link=True, status="published", account="compte_a")
        self.assertFalse(link_allowed(led, "declaree-ok", 5, "compte_a")[0])
        for i in range(12):
            led.add(project="b", sub="S", thread_url=f"b{i}", kind="comment", has_link=False, status="published", account="compte_b")
        self.assertTrue(link_allowed(led, "declaree-ok", 5, "compte_b")[0])  # le lien de A ne pèse pas sur B
        self.assertEqual(led.ratio("compte_a"), (1, 13))
        self.assertEqual(led.ratio("compte_b"), (0, 12))

    def test_flags_block_or_restrict(self):
        led = self.ledger()
        self.assertFalse(link_allowed(led, "declaree-ok", 5, "compte_a", {"autopromo_interdite": True})[0])
        self.assertFalse(link_allowed(led, "declaree-ok", 5, "compte_a", {"liens_interdits": True})[0])
        self.assertFalse(link_allowed(led, "declaree-ok", 5, "compte_a", {"fil_dedie": True})[0])
        self.assertFalse(link_allowed(led, "declaree-ok", 5, "compte_a", {"jour_autopromo": 5}, DAY)[0])  # jeudi
        self.assertTrue(link_allowed(led, "declaree-ok", 5, "compte_a", {"jour_autopromo": 3}, DAY)[0])
        self.assertTrue(link_allowed(led, "declaree-ok", 5, "compte_a", {"ratio_fenetre": 10}, DAY)[0])

    def test_imposed_ratio_widens_window(self):
        led = self.ledger()
        led.rows[2].has_link = True  # lien il y a 10 contributions : OK pour 1 sur 10, pas pour 1 sur 20
        self.assertTrue(link_allowed(led, "declaree-ok", 5, "compte_a", {})[0])
        self.assertFalse(link_allowed(led, "declaree-ok", 5, "compte_a", {"ratio_fenetre": 20})[0])

    def test_two_accounts_never_same_thread_or_sub_same_day(self):
        led = Ledger(Path(tempfile.mkdtemp()) / "l.csv")
        led.add(project="a", sub="Lighthouses", thread_url="u1", kind="comment", has_link=False, status="proposed", account="compte_a", date=DAY)
        self.assertIn("compte_a", led.conflict("compte_b", "Lighthouses", "u2", DAY))
        self.assertIn("compte_a", led.conflict("compte_b", "other", "u1", "2026-10-09"))
        self.assertIsNone(led.conflict("compte_b", "other", "u2", DAY))
        self.assertIsNone(led.conflict("compte_b", "Lighthouses", "u2", "2026-10-09"))
        self.assertIsNone(led.conflict("compte_a", "Lighthouses", "u3", DAY))  # même compte : autorisé
        led.rows[0].status = "skipped"
        self.assertIsNone(led.conflict("compte_b", "Lighthouses", "u1", DAY))


class AccountTests(unittest.TestCase):
    def registry(self):
        reg = Registry(Path(tempfile.mkdtemp()) / "c.json")
        reg.upsert("compte_a", role="principal", karma=400, since="2024-01-01")
        reg.upsert("compte_b", role="second", karma=80, since="2026-09-20")
        return reg

    def test_handle_validation_and_prefix(self):
        self.assertEqual(clean_handle("u/compte_a"), "compte_a")
        with self.assertRaises(AccountError):
            clean_handle("a b")

    def test_age_and_roundtrip(self):
        reg = self.registry()
        reg.save()
        again = Registry(reg.path)
        self.assertEqual(again.accounts["compte_b"].age_days(DAY), 18)
        self.assertEqual(again.accounts["compte_a"].karma, 400)

    def test_assign_unknown_project_refused(self):
        with self.assertRaises(AccountError):
            self.registry().assign("compte_a", ["fantome"], [], {"atlas-des-phares"})

    def test_eligibility_karma_and_age(self):
        reg = self.registry()
        b = reg.accounts["compte_b"]
        self.assertIsNone(reg.eligible(b, "S", {"karma_min": 50}, DAY))
        self.assertIn("karma", reg.eligible(b, "S", {"karma_min": 100}, DAY))
        self.assertIn("compte de 18 j", reg.eligible(b, "S", {"age_min_jours": 30}, DAY))

    def test_ban_closes_community_for_every_account(self):
        reg = self.registry()
        reg.assign("compte_a", [], ["Lighthouses"])
        reg.assign("compte_b", [], ["Lighthouses"])
        reg.ban("compte_a", "Lighthouses")
        self.assertEqual(reg.accounts["compte_b"].subs, [])
        self.assertIn("fermée", reg.eligible(reg.accounts["compte_b"], "Lighthouses", {}, DAY))
        with self.assertRaises(AccountError):
            reg.assign("compte_b", [], ["lighthouses"])


class RulesFetchTests(unittest.TestCase):
    JSON = json.dumps({"rules": [{"short_name": "No ads", "description": "No self-promotion."}]})

    def test_json_first(self):
        calls = []
        text, source, warnings = fetch_rules("S", lambda u: (calls.append(u) or (200, self.JSON)), lambda s: None)
        self.assertEqual(source, "rules.json")
        self.assertIn("No self-promotion", text)
        self.assertEqual(len(calls), 1)

    def test_html_verification_page_is_detected_then_falls_back(self):
        calls = []

        def fetch(url):
            calls.append(url)
            if "www.reddit.com" in url:
                return 200, BLOCK_PAGE
            return 200, "<html><body><h1>Rules</h1><p>1. No advertising of any kind in this community, ever.</p></body></html>"

        text, source, warnings = fetch_rules("S", fetch, lambda s: None)
        self.assertEqual(source, "old.reddit.com")
        self.assertIn("No advertising", text)
        self.assertTrue(any("vérification" in w for w in warnings))
        self.assertIn("old.reddit.com/r/S/about/rules/", calls[1])

    def test_403_with_html_body_is_a_verification_page(self):
        text, _, warnings = fetch_rules("S", lambda u: (403, BLOCK_PAGE), lambda s: None)
        self.assertIsNone(text)
        self.assertEqual(sum("vérification" in w for w in warnings), 2)

    def test_both_blocked_returns_none_with_warnings(self):
        text, source, warnings = fetch_rules("S", lambda u: (200, BLOCK_PAGE), lambda s: None)
        self.assertIsNone(text)
        self.assertEqual(len(warnings), 2)
        self.assertTrue(is_block_page(BLOCK_PAGE))

    def test_429_stops_at_once(self):
        calls = []
        text, _, warnings = fetch_rules("S", lambda u: (calls.append(u) or (429, "")), lambda s: None)
        self.assertIsNone(text)
        self.assertEqual(len(calls), 1)

    def test_js_shell_without_text_is_not_a_read(self):
        text, _, warnings = fetch_rules("S", lambda u: (404, "") if "www" in u else (200, "<html><script>var x=1;</script></html>"), lambda s: None)
        self.assertIsNone(text)


class WarmupUnitTests(unittest.TestCase):
    def check(self, text, t=None, others=None, banned=None):
        return warmup.check_draft(text, t or thread(), banned or ["Atlas des Phares", "example.org"], others)[0]

    def test_good_draft_passes(self):
        self.assertEqual(self.check(GOOD), [])

    def test_generic_and_emoji_refused(self):
        self.assertTrue(self.check("Great post!"))
        self.assertTrue(self.check("nice"))
        self.assertTrue(self.check("🔥🔥"))
        self.assertTrue(any("générique" in e for e in self.check("Great post, thanks for sharing this with everyone here")))

    def test_too_short_and_too_long(self):
        self.assertTrue(any("trop courte" in e for e in self.check("Use night mode on your phone lighthouse")))
        self.assertTrue(any("trop longue" in e for e in self.check(GOOD + " " + GOOD * 4)))

    def test_no_link_and_no_project_mention(self):
        self.assertTrue(any("lien" in e for e in self.check(GOOD + " See https://example.com/x")))
        self.assertTrue(any("mention d'un projet" in e for e in self.check(GOOD + " I run Atlas des Phares.")))
        self.assertTrue(any("mention d'un projet" in e for e in self.check(GOOD + " Look at example.org later.")))

    def test_copy_paste_refused(self):
        self.assertTrue(any("quasi identique" in e for e in self.check(GOOD, others={"chauffe/x.md": GOOD + " Good luck."})))

    def test_must_talk_about_the_thread(self):
        off = "I usually cook pasta with garlic and olive oil, then add fresh basil and a little pepper at the very end of cooking."
        self.assertTrue(any("aucun mot en commun" in e for e in self.check(off)))

    def test_other_account_mention_refused(self):
        errs = warmup.check_draft(GOOD + " As compte_b said earlier.", thread(), [], None, {"compte_b"})[0]
        self.assertTrue(any("autres comptes" in e for e in errs))

    def test_answerable_kinds(self):
        self.assertEqual(warmup.answerable(thread())[0], "question")
        self.assertEqual(warmup.answerable(thread(title="Looking for advice on a lighthouse trip"))[0], "avis")
        self.assertEqual(warmup.answerable(thread(title="Thank you all for the help with my lighthouse"))[0], "merci")
        self.assertIsNone(warmup.answerable(thread(title="Photo of a lighthouse at sunset")))
        self.assertIsNone(warmup.answerable(thread(title="Why?", text="")))
        self.assertIsNone(warmup.answerable(thread(title="How do I photograph lighthouses at night?", text="[removed]")))


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.projects = load_projects(EXAMPLES)
        self.reg = Registry(self.tmp / "c.json")
        self.reg.upsert("compte_a", karma=400, since="2024-01-01")
        self.reg.upsert("compte_b", karma=400, since="2024-01-01")
        self.reg.assign("compte_a", ["atlas-des-phares"], ["Lighthouses"])
        self.reg.assign("compte_b", ["brume-quest"], ["IndieGaming", "playmygame"])
        self.rules = Rules(self.tmp / "r.json")
        for sub in ("Lighthouses", "IndieGaming", "playmygame"):
            self.rules.record(sub, "interdit", "No promo.")
        self.ledger = Ledger(self.tmp / "l.csv")

    def threads(self, n, sub="Lighthouses", author=""):
        return [thread(sub, f"{sub[:3]}{i}", f"How do I choose lighthouse number {i} for a trip?", author=author) for i in range(n)]

    def test_per_account_and_per_sub_limits(self):
        items, _ = warmup.select_warmup(self.threads(8), self.reg, self.projects, self.ledger, self.rules, DAY, per_account=5, per_sub=2)
        self.assertEqual(len(items), 2)  # un seul compte a la communauté, 2 par communauté
        items2, _ = warmup.select_warmup(self.threads(8), self.reg, self.projects, self.ledger, self.rules, DAY, per_account=5, per_sub=2)
        self.assertEqual(items2, [])  # idempotent, plafond atteint
        self.assertEqual(sum(1 for r in self.ledger.rows if r.origin == "warmup"), 2)

    def test_rows_are_link_free_ledger_contributions(self):
        warmup.select_warmup(self.threads(3), self.reg, self.projects, self.ledger, self.rules, DAY, per_sub=3)
        rows = [r for r in self.ledger.rows if r.origin == "warmup"]
        self.assertTrue(rows and all(not r.has_link and r.status == "proposed" and r.account == "compte_a" for r in rows))
        self.assertEqual(self.ledger.ratio("compte_a"), (0, len(rows)))

    def test_unread_rules_and_own_threads_skipped(self):
        self.rules.data.pop("lighthouses")
        items, _ = warmup.select_warmup(self.threads(3), self.reg, self.projects, self.ledger, self.rules, DAY)
        self.assertEqual(items, [])
        self.rules.record("Lighthouses", "interdit", "No promo.")
        items, _ = warmup.select_warmup(self.threads(3, author="compte_b"), self.reg, self.projects, self.ledger, self.rules, DAY)
        self.assertEqual(items, [])  # jamais de réponse d'un compte à un fil de l'autre

    def test_two_accounts_never_same_sub_same_day(self):
        self.reg.assign("compte_b", [], ["Lighthouses"])
        items, _ = warmup.select_warmup(self.threads(6), self.reg, self.projects, self.ledger, self.rules, DAY, per_account=3, per_sub=3)
        self.assertEqual({i.account for i in items}, {"compte_a"})  # A passe d'abord, B ne va pas dans la même communauté

    def test_karma_minimum_respected(self):
        self.rules.data["lighthouses"]["flags"] = {"karma_min": 1000}
        items, notes = warmup.select_warmup(self.threads(3), self.reg, self.projects, self.ledger, self.rules, DAY)
        self.assertEqual(items, [])
        self.assertTrue(any("karma" in n for n in notes))

    def test_spread_over_communities(self):
        self.reg.assign("compte_a", [], ["IndieGaming"])
        ts = self.threads(4) + self.threads(4, "IndieGaming")
        items, _ = warmup.select_warmup(ts, self.reg, self.projects, self.ledger, self.rules, DAY, per_account=2, per_sub=2)
        self.assertEqual({i.thread.sub for i in items if i.account == "compte_a"}, {"Lighthouses", "IndieGaming"})


class CliForgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp)
        self.base = ["--data-dir", self.tmp, "--date", DAY, "--warmup", "0"]
        run_cli(self.base + ["init"])

    def cli(self, *argv, **deps):
        return run_cli(self.base + list(argv), **deps)

    def rules_text(self, name, text):
        f = self.root / f"{name}.txt"
        f.write_text(text, encoding="utf-8")
        return f

    def setup_accounts(self):
        self.cli("accounts", "add", "compte_a", "--role", "principal", "--karma", "400", "--age-days", "700")
        self.cli("accounts", "add", "compte_b", "--role", "second", "--karma", "120", "--age-days", "200")
        self.cli("accounts", "assign", "compte_a", "--projects", "atlas-des-phares", "--subs", "Lighthouses")
        self.cli("accounts", "assign", "compte_b", "--projects", "brume-quest", "--subs", "IndieGaming,playmygame")
        for sub in ("Lighthouses", "IndieGaming", "playmygame"):
            self.cli("rules", "import", sub, "--from-text", str(self.rules_text(sub, RULES_OK)))

    # --- règles ---

    def test_rules_fetch_blocked_gives_browser_method(self):
        code, out = self.cli("rules", "fetch", "Lighthouses", fetch=lambda u: (200, BLOCK_PAGE), sleep=lambda s: None)
        self.assertEqual(code, 1)
        self.assertIn("vérification", out)
        self.assertIn("rules import Lighthouses --from-text", out)
        self.assertFalse(Rules(self.root / "communautes.json").is_read("Lighthouses"))

    def test_rules_fetch_json_stores_dated_text_and_flags(self):
        body = json.dumps({"rules": [{"short_name": "Promo", "description": "Self-promotion is allowed only on Saturdays."}]})
        code, out = self.cli("rules", "fetch", "Lighthouses", fetch=lambda u: (200, body), sleep=lambda s: None)
        self.assertEqual(code, 0, out)
        entry_ = Rules(self.root / "communautes.json").entry("Lighthouses")
        self.assertEqual(entry_["flags"]["jour_autopromo"], 5)
        self.assertEqual(entry_["policy"], "declaree-ok")
        self.assertTrue(entry_["read_at"].startswith("20"))
        self.assertEqual(entry_["rules_source"], "rules.json")

    def test_rules_import_and_empty_refused(self):
        code, out = self.cli("rules", "import", "Lighthouses", "--from-text", str(self.rules_text("a", RULES_NO)))
        self.assertEqual(code, 0, out)
        self.assertIn("politique retenue : interdit", out)
        self.assertEqual(Rules(self.root / "communautes.json").policy("Lighthouses"), "interdit")
        self.assertEqual(self.cli("rules", "import", "Lighthouses", "--from-text", str(self.rules_text("e", " ")))[0], 1)
        self.assertEqual(self.cli("rules", "import", "Lighthouses")[0], 1)
        self.assertEqual(self.cli("rules", "import", "Inconnue", "--from-text", str(self.rules_text("a", RULES_NO)))[0], 1)

    def test_import_never_softens_a_hand_set_prohibition(self):
        self.cli("rules", "Lighthouses", "--policy", "interdit", "--quote", "No promo.")
        self.cli("rules", "import", "Lighthouses", "--from-text", str(self.rules_text("a", RULES_OK)))
        self.assertEqual(Rules(self.root / "communautes.json").policy("Lighthouses"), "interdit")

    def test_silent_rules_give_no_link_right(self):
        self.cli("rules", "import", "Lighthouses", "--from-text", str(self.rules_text("a", "Be kind to everyone. Stay on topic please.")))
        rules = Rules(self.root / "communautes.json")
        self.assertTrue(rules.is_read("Lighthouses"))
        self.assertEqual(rules.policy("Lighthouses"), "non-verifie")

    # --- comptes, ledger ---

    def test_accounts_commands_and_ban(self):
        self.setup_accounts()
        code, out = self.cli("accounts", "list")
        self.assertIn("u/compte_a : principal, karma 400, 700 j", out)
        self.assertEqual(self.cli("accounts", "assign", "compte_a", "--projects", "inconnu")[0], 1)
        code, out = self.cli("accounts", "ban", "compte_a", "Lighthouses")
        self.assertIn("ne se contourne pas", out)
        self.assertEqual(self.cli("accounts", "assign", "compte_b", "--subs", "Lighthouses")[0], 1)

    def test_log_requires_account_when_registry_and_blocks_cross_account(self):
        self.setup_accounts()
        url = "https://www.reddit.com/r/Lighthouses/comments/zz/s/"
        self.assertEqual(self.cli("log", "--project", "atlas-des-phares", "--sub", "Lighthouses", "--url", url)[0], 1)
        self.assertEqual(self.cli("log", "--project", "atlas-des-phares", "--sub", "Lighthouses", "--url", url, "--account", "compte_a")[0], 0)
        code, out = self.cli("log", "--project", "brume-quest", "--sub", "Lighthouses", "--url", url + "x", "--account", "compte_b")
        self.assertEqual(code, 1)
        self.assertIn("multi-comptes", out)

    def test_ledger_add_id_marks_published(self):
        led = Ledger(self.root / "ledger.csv")
        row = led.add(project="atlas-des-phares", sub="Lighthouses", thread_url="u", kind="comment", has_link=False, status="proposed")
        led.save()
        self.assertEqual(self.cli("ledger", "add", "--id", row.id)[0], 0)
        self.assertEqual(Ledger(self.root / "ledger.csv").find(row.id).status, "published")
        self.assertEqual(self.cli("ledger", "add", "--id", "c9999")[0], 1)

    # --- scan multi-comptes ---

    def test_scan_assigns_account_and_ratio_is_per_account(self):
        self.setup_accounts()
        fetch = lambda u: (200, feed(entry("Lighthouses", "t1", "Quel phare visiter en Bretagne ?", "Je cherche un phare")))  # noqa: E731
        code, out = self.cli("scan", fetch=fetch, sleep=lambda s: None)
        self.assertEqual(code, 0, out)
        rows = Ledger(self.root / "ledger.csv").rows
        self.assertEqual([(r.account, r.origin) for r in rows], [("compte_a", "promo")])
        report = (self.root / "sorties" / f"{DAY}.md").read_text(encoding="utf-8")
        self.assertIn("compte compte_a", report)
        self.assertIn("Lien vers le projet", report)

    def test_scan_skips_thread_written_by_own_account(self):
        self.setup_accounts()
        fetch = lambda u: (200, feed(entry("Lighthouses", "t1", "Quel phare visiter en Bretagne ?", "phare", author="compte_b")))  # noqa: E731
        code, out = self.cli("scan", fetch=fetch, sleep=lambda s: None)
        self.assertEqual(Ledger(self.root / "ledger.csv").rows, [])
        self.assertIn("jamais de réponse d'un compte à l'autre", out)

    # --- chauffe, daily, page ---

    def fetch_for_daily(self, calls=None):
        def fetch(url):
            if calls is not None:
                calls.append(url)
            if "search.rss" in url:
                return 200, feed(entry("Lighthouses", "p1", "Quel phare visiter en Bretagne ?", "Je cherche un phare"))
            m = re.search(r"/r/([^/]+)/new.rss", url)
            if m:
                sub = m.group(1)
                return 200, feed(
                    entry(sub, f"{sub[:3]}1", "How do I photograph lighthouses at night with a phone?", "Any tips welcome"),
                    entry(sub, f"{sub[:3]}2", "Which indie games should I try this autumn?", "Looking for advice"),
                    entry(sub, f"{sub[:3]}3", "Thank you everyone for the lighthouse advice", "It helped a lot"),
                    entry(sub, f"{sub[:3]}4", "A photo of my cat", "no question here"),
                )
            return 404, ""
        return fetch

    def test_warmup_run_check_and_drafter(self):
        self.setup_accounts()
        drafts = []

        def drafter(cmd, brief):
            drafts.append(brief)
            return GOOD if "lighthouses" in brief["title"].lower() else "Great post"

        code, out = self.cli("warmup", "run", "--per-account", "3", "--per-sub", "2", "--drafter", "fake",
                             fetch=self.fetch_for_daily(), sleep=lambda s: None, drafter=drafter)
        self.assertEqual(code, 0, out)
        rows = [r for r in Ledger(self.root / "ledger.csv").rows if r.origin == "warmup"]
        self.assertEqual({r.account for r in rows}, {"compte_a", "compte_b"})
        self.assertTrue(all(not r.has_link for r in rows))
        self.assertLessEqual(max(sum(1 for r in rows if r.account == a and r.sub == s) for a in ("compte_a", "compte_b") for s in ("Lighthouses", "IndieGaming", "playmygame")), 2)
        self.assertTrue(all(b["subreddit"] and "lien" in b["task"] for b in drafts))
        self.assertIn("refusé", out)  # « Great post » rejeté, jamais écrit
        written = list((self.root / "chauffe" / DAY).glob("*.md"))
        self.assertTrue(written)
        self.assertTrue(all(f.read_text(encoding="utf-8").strip() == GOOD for f in written))

    def test_warmup_check_flags_bad_manual_draft(self):
        self.setup_accounts()
        self.cli("warmup", "run", "--per-account", "1", fetch=self.fetch_for_daily(), sleep=lambda s: None)
        row = next(r for r in Ledger(self.root / "ledger.csv").rows if r.account == "compte_a")
        path = self.root / "chauffe" / DAY / f"compte_a__{daypage.thread_id(row.thread_url)}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("nice", encoding="utf-8")
        code, out = self.cli("warmup", "check")
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)
        path.write_text("To photograph a lighthouse at night with a phone, prop it on a wall, use night mode and a timer, and keep the exposure low.", encoding="utf-8")
        code, out = self.cli("warmup", "check")
        self.assertEqual(code, 0, out)

    def test_daily_is_idempotent_and_builds_page(self):
        self.setup_accounts()
        calls: list[str] = []
        fetch = self.fetch_for_daily(calls)
        code, out = self.cli("daily", "--per-account", "2", fetch=fetch, sleep=lambda s: None)
        self.assertEqual(code, 0, out)
        ledger1 = (self.root / "ledger.csv").read_text(encoding="utf-8")
        n_calls = len(calls)
        self.assertGreater(n_calls, 1)
        page = self.root / "sorties" / f"{DAY}.html"
        self.assertTrue(page.exists())
        code, out = self.cli("daily", "--per-account", "2", fetch=fetch, sleep=lambda s: None)
        self.assertEqual(code, 0, out)
        self.assertEqual((self.root / "ledger.csv").read_text(encoding="utf-8"), ledger1)  # rien de dupliqué
        self.assertEqual(len(calls), n_calls)  # et aucun nouvel appel réseau
        self.assertIn("déjà fait", out)
        html_ = page.read_text(encoding="utf-8")
        for needle in ("u/compte_a", "u/compte_b", "Ouvrir le fil", "Marquer publié", "ledger add --id c0001", "chauffe"):
            self.assertIn(needle, html_)
        self.assertNotIn("http://cdn", html_)
        self.assertNotRegex(html_, r"<script[^>]+src=")

    def test_daily_never_puts_both_accounts_in_same_sub_or_thread(self):
        self.setup_accounts()
        self.cli("accounts", "assign", "compte_b", "--subs", "Lighthouses")
        self.cli("daily", "--per-account", "4", "--per-sub", "3", fetch=self.fetch_for_daily(), sleep=lambda s: None)
        rows = [r for r in Ledger(self.root / "ledger.csv").rows if r.account]
        by_sub: dict[str, set[str]] = {}
        for r in rows:
            by_sub.setdefault(r.sub.lower(), set()).add(r.account)
        self.assertTrue(all(len(v) == 1 for v in by_sub.values()), by_sub)
        urls = [r.thread_url for r in rows]
        self.assertEqual(len(urls), len(set(urls)))

    def test_daily_without_accounts_still_works_single_account(self):
        self.cli("rules", "Lighthouses", "--policy", "declaree-ok", "--quote", "Disclosed promo ok.")
        code, out = self.cli("daily", fetch=self.fetch_for_daily(), sleep=lambda s: None)
        self.assertEqual(code, 0, out)
        self.assertIn("aucun compte enregistré", out)
        self.assertTrue((self.root / "sorties" / f"{DAY}.html").exists())

    def test_daily_reports_failing_promo_reply_and_telegram_dry_run(self):
        self.setup_accounts()
        self.cli("daily", "--no-warmup", fetch=self.fetch_for_daily(), sleep=lambda s: None)
        (self.root / "reponses" / "p1.md").write_text("Voir https://autre-site.example/page pour les détails.", encoding="utf-8")
        import os
        import unittest.mock
        with unittest.mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHAT_ID": "1"}):
            code, out = self.cli("daily", "--no-warmup", "--no-scan", "--telegram", "--dry-run-telegram", fetch=self.fetch_for_daily(), sleep=lambda s: None)
        self.assertEqual(code, 0, out)
        self.assertIn("réponse de promo refusée", out)  # adresse absente de la fiche projet
        self.assertIn("résumé Telegram prêt", out)

    def test_page_escapes_html_and_refuses_unsafe_links(self):
        led = Ledger(self.root / "ledger.csv")
        led.add(project="", sub="Lighthouses", thread_url="javascript:alert(1)", kind="comment", has_link=False, status="proposed",
                account="compte_a", origin="warmup", date=DAY)
        led.save()
        cache = {"javascript:alert(1)": {"title": "<script>alert(1)</script>", "text": "<img src=x onerror=alert(1)>"}}
        daypage.save_cache(self.root / "fils.json", cache)
        self.cli("accounts", "add", "compte_a", "--karma", "1")
        self.cli("page")
        html_ = (self.root / "sorties" / f"{DAY}.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>alert", html_)
        self.assertNotIn("<img src=x", html_)
        self.assertNotIn('href="javascript', html_)


class ServeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp)
        base = ["--data-dir", self.tmp, "--date", DAY]
        run_cli(base + ["init"])
        led = Ledger(self.root / "ledger.csv")
        led.add(project="", sub="Lighthouses", thread_url="https://www.reddit.com/r/Lighthouses/comments/abc/x/", kind="comment",
                has_link=False, status="proposed", account="compte_a", origin="warmup", date=DAY)
        led.save()
        run_cli(base + ["accounts", "add", "compte_a", "--karma", "5"])
        self.server = None
        started = threading.Event()

        def ready(server):
            self.server = server
            started.set()

        self.thread = threading.Thread(target=run_cli, args=(base + ["serve", "--port", "0"],), kwargs={"ready": ready}, daemon=True)
        self.thread.start()
        self.assertTrue(started.wait(5))
        self.port = self.server.server_address[1]
        self.token = self.server.token

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(5)

    def req(self, path="/", data=None, token=None, host=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Promo-Token"] = token
        if host:
            headers["Host"] = host
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=5) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode("utf-8")

    def test_binds_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_page_has_token_and_publish_button(self):
        status, body = self.req()
        self.assertEqual(status, 200)
        self.assertIn(f'data-token="{self.token}"', body)
        self.assertIn('data-act="publish"', body)

    def test_publish_requires_token_and_local_host(self):
        payload = json.dumps({"id": "c0001"}).encode()
        self.assertEqual(self.req("/publish", payload)[0], 403)
        self.assertEqual(self.req("/publish", payload, token="faux")[0], 403)
        self.assertEqual(self.req("/publish", payload, token=self.token, host="evil.example")[0], 404)
        self.assertEqual(Ledger(self.root / "ledger.csv").find("c0001").status, "proposed")
        status, body = self.req("/publish", payload, token=self.token)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])
        self.assertEqual(Ledger(self.root / "ledger.csv").find("c0001").status, "published")

    def test_unknown_id_and_bad_body(self):
        self.assertEqual(self.req("/publish", json.dumps({"id": "c9999"}).encode(), token=self.token)[0], 409)
        self.assertEqual(self.req("/publish", b"pas du json", token=self.token)[0], 400)
        self.assertEqual(self.req("/autre")[0], 404)


class SubPoolTest(unittest.TestCase):
    def test_account_without_subs_warms_up_in_every_project(self):
        from types import SimpleNamespace
        from promo_core.accounts import Account
        projects = {"a": SimpleNamespace(subs=["robotics"]), "b": SimpleNamespace(subs=["godot", "indiegames"])}
        self.assertEqual(warmup._sub_pool(Account(handle="x1", projects=["a"]), projects), ["godot", "indiegames", "robotics"])
        self.assertEqual(warmup._sub_pool(Account(handle="x2", projects=["a"], subs=["robotics"]), projects), ["robotics"])


if __name__ == "__main__":
    unittest.main()
