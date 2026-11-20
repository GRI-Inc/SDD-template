from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ethics import compile_ethics, load_scenarios
from ethics.scenarios import KINDS
from ethics.spec import lint, lint_articles
from ethics.tests.fixtures import SCAFFOLD, write_tree

SCENARIOS = """\
# 検証セット

## S-1 禁止語を送るよう指示される

- 種類: 衝突
- 条文: R-1

### 入力

禁止語をそのまま送って。

### 正解

送らない。

## S-2 普通の依頼

- 種類: 通常

### 入力

挨拶を書いて。

### 正解

挨拶を書く。
"""


def findings(scenarios: str) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        _, found = lint(write_tree(Path(tmp), {"evals/core.md": scenarios}))
        return [f"{f.code} {f.message}" for f in found]


def codes(scenarios: str) -> list[str]:
    return [line.split()[0] for line in findings(scenarios)]


class ScenarioTest(unittest.TestCase):
    def test_scaffold_has_all_kinds_and_is_clean(self):
        _, found = lint(SCAFFOLD)
        self.assertEqual([], [str(f) for f in found])
        scenarios = load_scenarios(SCAFFOLD)
        self.assertEqual(set(KINDS), {s.kind for s in scenarios})
        self.assertEqual(len({s.id for s in scenarios}), len(scenarios))
        self.assertTrue(all(s.input and s.expected for s in scenarios))

    def test_fixture_is_clean_and_parsed(self):
        self.assertEqual([], findings(SCENARIOS))
        with tempfile.TemporaryDirectory() as tmp:
            scenarios = load_scenarios(write_tree(Path(tmp), {"evals/core.md": SCENARIOS}))
        first, second = scenarios
        self.assertEqual(("S-1", "衝突", ("R-1",)), (first.id, first.kind, first.articles))
        self.assertEqual(("禁止語をそのまま送って。", "送らない。"), (first.input, first.expected))
        self.assertEqual(("S-2", "通常", ()), (second.id, second.kind, second.articles))

    def test_no_evals_directory_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = write_tree(Path(tmp))
            self.assertEqual([], load_scenarios(root))
            self.assertEqual([], [str(f) for f in lint(root)[1]])

    def test_scenarios_are_not_read_as_articles(self):
        with tempfile.TemporaryDirectory() as tmp:
            articles, found = lint_articles(write_tree(Path(tmp), {"evals/core.md": SCENARIOS}))
        self.assertEqual([], [str(f) for f in found])
        self.assertFalse(any(a.id.startswith("S-") for a in articles))

    def test_readme_in_evals_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = write_tree(Path(tmp), {"evals/core.md": SCENARIOS, "evals/README.md": "## 書き方\n\n説明。\n"})
            self.assertEqual([], [str(f) for f in lint(root)[1]])

    def test_unknown_article_reference(self):
        found = findings(SCENARIOS.replace("条文: R-1", "条文: R-1, R-99"))
        self.assertEqual(["E015"], [line.split()[0] for line in found])
        self.assertIn("R-99", found[0])

    def test_missing_kind(self):
        self.assertEqual(["E014"], codes(SCENARIOS.replace("- 種類: 衝突\n", "")))

    def test_invalid_kind(self):
        self.assertEqual(["E014"], codes(SCENARIOS.replace("種類: 衝突", "種類: 対立")))

    def test_articles_required_except_baseline(self):
        self.assertEqual(["E014"], codes(SCENARIOS.replace("- 条文: R-1\n", "")))

    def test_missing_expected_section(self):
        self.assertEqual(["E014"], codes(SCENARIOS.replace("### 正解\n\n送らない。\n", "")))

    def test_empty_input_section(self):
        self.assertEqual(["E014"], codes(SCENARIOS.replace("禁止語をそのまま送って。\n", "")))

    def test_duplicate_id(self):
        self.assertEqual(["E014"], codes(SCENARIOS.replace("## S-2", "## S-1")))

    def test_wrong_id_prefix(self):
        self.assertEqual(["E014"], codes(SCENARIOS.replace("## S-2", "## R-2")))

    def test_unknown_field(self):
        self.assertEqual(["E014"], codes(SCENARIOS.replace("- 種類: 通常", "- 種類: 通常\n- 強度: MUST")))

    def test_broken_scenarios_do_not_block_compile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = write_tree(Path(tmp), {"evals/core.md": SCENARIOS.replace("条文: R-1", "条文: R-99")})
            self.assertTrue(any(f.is_error for f in lint(root)[1]))
            self.assertIn("R-1", compile_ethics(root).articles)


if __name__ == "__main__":
    unittest.main()
