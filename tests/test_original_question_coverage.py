import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "original_question_coverage.py"
SPEC = importlib.util.spec_from_file_location("original_question_coverage", MODULE_PATH)
assert SPEC and SPEC.loader
COVERAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COVERAGE)


class OriginalQuestionCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = COVERAGE.build_inventory(ROOT)
        cls.by_no = {row["q_no"]: row for row in cls.inventory["questions"]}

    def test_every_source_question_has_one_coverage_row(self):
        self.assertEqual(307, len(self.by_no))
        self.assertEqual(set(range(1, 308)), set(self.by_no))

    def test_statuses_are_exhaustive(self):
        summary = self.inventory["summary"]
        total = sum(summary[key] for key in ("attempted", "ready_unseen", "needs_audit", "blocked"))
        self.assertEqual(307, total)

    def test_repairs_do_not_count_as_original_attempts(self):
        attempts = COVERAGE.exact_original_attempts(ROOT / "10-逐题作答记录.csv")
        self.assertTrue(all(COVERAGE.EXACT_ORIGINAL.fullmatch(f"TQ-{q_no:03d}") for q_no in attempts))
        self.assertEqual(len(attempts), self.inventory["summary"]["attempted"])

    def test_known_examples_distinguish_mapping_from_exposure(self):
        self.assertEqual("attempted", self.by_no[9]["coverage_status"])
        self.assertEqual("ready_unseen", self.by_no[1]["coverage_status"])
        self.assertEqual(0, self.by_no[1]["attempt_count"])

    def test_selector_only_returns_ready_unseen(self):
        selected = COVERAGE.select_candidates(self.inventory, bok="III.D", limit=10)
        self.assertTrue(selected)
        self.assertTrue(all(row["coverage_status"] == "ready_unseen" for row in selected))
        self.assertTrue(
            all(any(link["indicator_id"].startswith("III.D") for link in row["indicators"]) for row in selected)
        )

    def test_every_needs_audit_question_has_a_readable_primary_rule(self):
        pending = [
            row for row in self.inventory["questions"]
            if row["coverage_status"] == "needs_audit"
        ]
        self.assertTrue(pending)
        self.assertTrue(all(row["primary_rules"] for row in pending))
        self.assertTrue(
            all(rule["article"] and rule["concept"] for row in pending for rule in row["primary_rules"])
        )

    def test_audit_queue_contains_all_pending_question_ids(self):
        rendered = COVERAGE.render_audit_queue(self.inventory)
        for row in self.inventory["questions"]:
            if row["coverage_status"] == "needs_audit":
                self.assertIn(row["question_id"], rendered)

    def test_article_summary_separates_primary_and_related_questions(self):
        summary = COVERAGE.article_summary(self.inventory, "3")
        self.assertGreater(summary["primary_total"], 0)
        self.assertEqual(
            summary["primary_total"],
            sum(summary[key] for key in ("attempted", "ready_unseen", "needs_audit", "blocked")),
        )
        self.assertGreaterEqual(summary["related_only"], 0)

    def test_article_selector_does_not_confuse_article_3_and_30(self):
        selected = COVERAGE.select_candidates(self.inventory, article="3", limit=50)
        self.assertTrue(selected)
        self.assertTrue(all(
            any(COVERAGE.matches_article(rule["article"], "3") for rule in row["primary_rules"])
            for row in selected
        ))


if __name__ == "__main__":
    unittest.main()
