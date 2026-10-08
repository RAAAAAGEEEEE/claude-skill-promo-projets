"""Tests du mode Retours (retours constructifs). Données fictives uniquement."""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import promo  # noqa: E402
from promo_core import feedback  # noqa: E402


class FeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "retours.csv"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_add_and_summary_sorted_by_severity(self) -> None:
        feedback.add(self.path, "2026-10-08", "demo", "r/exemple", "idee", 1, "ajouter un mode sombre pour la nuit")
        feedback.add(self.path, "2026-10-08", "demo", "r/exemple", "bug", 3, "le clavier cache la grille sur mobile")
        text = feedback.summary(self.path, "demo")
        self.assertIn("Par type", text)
        self.assertLess(text.index("clavier"), text.index("mode sombre"))
        self.assertNotIn("r/", feedback._read(self.path)[0]["source"])

    def test_rejects_bad_input(self) -> None:
        with self.assertRaises(feedback.FeedbackError):
            feedback.add(self.path, "2026-10-08", "demo", "", "nimporte", 2, "texte assez long ici")
        with self.assertRaises(feedback.FeedbackError):
            feedback.add(self.path, "2026-10-08", "demo", "", "bug", 5, "texte assez long ici")
        with self.assertRaises(feedback.FeedbackError):
            feedback.add(self.path, "2026-10-08", "demo", "", "bug", 2, "court")

    def test_discarded_feedback_leaves_summary(self) -> None:
        feedback.add(self.path, "2026-10-08", "demo", "", "bug", 2, "le bouton valider ne répond pas")
        feedback.set_status(self.path, 1, "ecarte")
        self.assertEqual(feedback.summary(self.path), "Aucun retour enregistré.")

    def test_cli_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = promo.main(["--data-dir", root, "init"])
                code |= promo.main(["--data-dir", root, "feedback", "add", "--project", "inconnu", "--kind", "bug", "--text", "texte assez long"])
            self.assertEqual(code, 1)
            self.assertIn("projet inconnu", out.getvalue())


if __name__ == "__main__":
    unittest.main()
