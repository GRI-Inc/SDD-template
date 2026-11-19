from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ethic_layer.spec import lint
from ethic_layer.tests.fixtures import CUSTOMS, IDEALS, PRINCIPLES, RULES, SCAFFOLD, write_tree


def codes(overrides: dict | None = None) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        _, findings = lint(write_tree(Path(tmp), overrides))
        return [f.code for f in findings]


class LintTest(unittest.TestCase):
    def test_scaffold_is_clean(self):
        articles, findings = lint(SCAFFOLD)
        self.assertEqual([], [str(f) for f in findings])
        self.assertEqual(12, len(articles))

    def test_fixture_is_clean(self):
        self.assertEqual([], codes())

    def test_body_and_sections_are_captured(self):
        articles, _ = lint(SCAFFOLD)
        r1 = next(a for a in articles if a.id == "R-1")
        self.assertIn("組織外の宛先へ送るツール呼び出し", r1.body)
        self.assertNotIn("適合例", r1.body)
        self.assertTrue(any("翻訳 API" in line for line in r1.sections["違反例"]))

    def test_missing_frontmatter(self):
        self.assertIn("E001", codes({"00-ideals.md": "## I-1 題名\n\n本文。\n"}))

    def test_misplaced_file(self):
        self.assertIn("E002", codes({"30-customs/extra.md": RULES.replace("R-", "R-9")}))

    def test_heading_without_id(self):
        self.assertIn("E003", codes({"00-ideals.md": IDEALS + "\n## 番号なし\n\n本文。\n"}))

    def test_prefix_mismatch(self):
        self.assertIn("E004", codes({"30-customs/core.md": CUSTOMS.replace("## C-1", "## P-9")}))

    def test_duplicate_id(self):
        self.assertIn("E005", codes({"00-ideals.md": IDEALS + "\n## I-1 重複\n\n本文。\n"}))

    def test_missing_required_field(self):
        self.assertIn("E006", codes({"10-principles/core.md": PRINCIPLES.replace("- 検査: judge\n", "")}))

    def test_field_not_allowed_in_tier(self):
        self.assertIn("E007", codes({"30-customs/core.md": CUSTOMS.replace("- 検査: judge", "- 違反時: block")}))

    def test_invalid_values(self):
        self.assertIn("E008", codes({"10-principles/core.md": PRINCIPLES.replace("MUST", "SHOULD")}))
        self.assertIn("E008", codes({"20-rules/core.md": RULES.replace("- 違反時: block", "- 違反時: delete")}))
        self.assertIn("E008", codes({"20-rules/core.md": RULES.replace("- 適用点: output", "- 適用点: later")}))
        self.assertIn("E008", codes({"20-rules/core.md": RULES.replace("- 検査: judge", "- 検査: llm")}))

    def test_unknown_basis(self):
        self.assertIn("E009", codes({"10-principles/core.md": PRINCIPLES.replace("根拠: I-1", "根拠: I-9")}))

    def test_basis_must_be_higher_tier(self):
        self.assertIn("E010", codes({"20-rules/core.md": RULES.replace("- 根拠: P-1\n- 適用点: output", "- 根拠: C-1\n- 適用点: output")}))
        self.assertIn("E010", codes({"20-rules/core.md": RULES.replace("- 根拠: P-1\n- 適用点: output", "- 根拠: R-1\n- 適用点: output")}))

    def test_missing_guard_file(self):
        self.assertIn("E011", codes({"guards/forbidden.py": None}))

    def test_missing_body(self):
        self.assertIn("E012", codes({"00-ideals.md": "---\ntier: ideal\n---\n## I-1 題名\n"}))

    def test_no_articles(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, findings = lint(Path(tmp))
            self.assertEqual(["E013"], [f.code for f in findings])

    def test_ideal_without_rule_descendant(self):
        self.assertIn("W001", codes({"00-ideals.md": IDEALS + "\n## I-2 孤立\n\n本文。\n"}))

    def test_too_many_ideals(self):
        extra = "".join(f"\n## I-{n} 追加\n\n本文。\n" for n in range(2, 9))
        self.assertIn("W002", codes({"00-ideals.md": IDEALS + extra}))

    def test_rule_without_examples(self):
        self.assertIn("W003", codes({"20-rules/core.md": RULES.replace("### 違反例", "### その他")}))

    def test_headings_in_code_fence_and_comment_are_ignored(self):
        text = IDEALS + "\n```\n## これは見出しではない\n```\n\n<!--\n## これも違う\n-->\n"
        self.assertEqual([], codes({"00-ideals.md": text}))


if __name__ == "__main__":
    unittest.main()
