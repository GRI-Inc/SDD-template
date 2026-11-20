from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from ethics import compile_ethics, coverage
from ethics.cli import main
from ethics.coverage import DETECTED, ENFORCED, MEASURED, UNCOVERED, render, summarize
from ethics.tests.fixtures import CUSTOMS, RULES, SCAFFOLD, write_tree


def levels(overrides: dict | None = None, judge: bool = False) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        compiled = compile_ethics(write_tree(Path(tmp), overrides))
        return {row.id: row.level for row in coverage(compiled, judge=judge)}


class CoverageTest(unittest.TestCase):
    def test_scaffold_without_judge(self):
        rows = coverage(compile_ethics(SCAFFOLD))
        self.assertEqual(30, len(rows))
        self.assertEqual(["R-1"], [r.id for r in rows if r.level == ENFORCED])
        uncovered = {r.id for r in rows if r.level == UNCOVERED}
        self.assertEqual(29, len(uncovered))
        self.assertEqual(4, sum(1 for r in rows if r.tier == "ideal" and r.id in uncovered))
        self.assertEqual(8, sum(1 for r in rows if r.tier == "custom" and r.id in uncovered))
        self.assertTrue({"R-4", "R-5", "R-9"} <= uncovered)
        for row in rows:
            if row.id in ("R-4", "R-5", "R-9"):
                self.assertIn("適用点 pr", row.reason)

    def test_scaffold_with_judge(self):
        rows = coverage(compile_ethics(SCAFFOLD), judge=True)
        counts = summarize(rows)
        self.assertEqual({ENFORCED: 1, DETECTED: 0, MEASURED: 18, UNCOVERED: 11}, counts)
        # 判定器があっても、適用点 pr の条文と、検査を持たない慣習は扱われない。
        uncovered = {r.id for r in rows if r.level == UNCOVERED}
        self.assertTrue({"R-4", "R-5", "R-9"} <= uncovered)
        self.assertEqual(8, sum(1 for r in rows if r.tier == "custom" and r.id in uncovered))

    def test_rows_follow_tier_order(self):
        rows = coverage(compile_ethics(SCAFFOLD))
        order = ["ideal", "principle", "rule", "custom"]
        self.assertEqual(sorted(rows, key=lambda r: order.index(r.tier)), rows)

    def test_fixture_levels(self):
        self.assertEqual(
            {"I-1": UNCOVERED, "P-1": UNCOVERED, "R-1": ENFORCED, "R-2": UNCOVERED, "C-1": UNCOVERED}, levels()
        )
        self.assertEqual(
            {"I-1": MEASURED, "P-1": MEASURED, "R-1": ENFORCED, "R-2": MEASURED, "C-1": MEASURED}, levels(judge=True)
        )

    def test_output_guard_with_refine_is_only_measured(self):
        # 出力のガードは、違反時 block のときだけ止める。refine は未実装なので記録だけになる。
        rules = RULES.replace("- 適用点: tool_call", "- 適用点: output")
        self.assertEqual(ENFORCED, levels({"20-rules/core.md": rules})["R-1"])
        rules = rules.replace("- 違反時: block", "- 違反時: refine")
        self.assertEqual(MEASURED, levels({"20-rules/core.md": rules})["R-1"])

    def test_plan_only_article_is_uncovered(self):
        rules = RULES.replace("- 適用点: output", "- 適用点: plan")
        self.assertEqual(UNCOVERED, levels({"20-rules/core.md": rules}, judge=True)["R-2"])

    def test_custom_without_check_is_uncovered_even_with_judge(self):
        customs = CUSTOMS.replace("- 検査: judge\n", "")
        self.assertEqual(UNCOVERED, levels({"30-customs/core.md": customs}, judge=True)["C-1"])

    def test_render_lists_every_article_and_totals(self):
        compiled = compile_ethics(SCAFFOLD)
        text = render(coverage(compiled), judge=False)
        for article_id in compiled.articles:
            self.assertIn(f" {article_id} ", text)
        self.assertIn("条文 30 件: 強制 1、検出 0、測定 0、対象外 29", text)

    def test_cli(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["coverage", str(SCAFFOLD), "--judge"])
        self.assertEqual(0, code)
        self.assertIn("設定: 判定器あり", out.getvalue())
        self.assertIn("## 測定（18 件）", out.getvalue())


if __name__ == "__main__":
    unittest.main()
