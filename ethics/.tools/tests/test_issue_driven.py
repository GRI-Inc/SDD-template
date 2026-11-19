"""Issue 駆動の運用に使う部分（プロンプトへの同期、Pull Request のガード）のテスト。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ethics import compile_ethics
from ethics.cli import main
from ethics.prcheck import build_event, check_pr, report, unchecked
from ethics.sync import BEGIN, DEFAULT_TARGETS, END, SyncError, sync_file, sync_text
from ethics.tests.fixtures import CUSTOMS, REPO_ROOT, SCAFFOLD, write_tree

GOOD_BODY = """\
## 関連する仕様

[SPEC.md](spec-ai-writer/docs/SPEC.md)

## 仕様差分

- 変更なし

## 関連 Issue

Fixes #12
"""


class SyncTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = write_tree(Path(self._tmp.name) / "ethics")
        self.compiled = compile_ethics(self.root)
        self.target = Path(self._tmp.name) / "WORKFLOW.md"
        self.target.write_text(f"前文\n\n{BEGIN}\n古い内容\n{END}\n\n後文\n", encoding="utf-8")

    def test_sync_replaces_only_the_marked_region(self):
        self.assertTrue(sync_file(self.target, self.compiled))
        text = self.target.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("前文\n\n" + BEGIN))
        self.assertTrue(text.endswith(END + "\n\n後文\n"))
        self.assertNotIn("古い内容", text)
        for expected in ("I-1 信頼を損なわない", "R-1 [MUST NOT] 禁止語を外部へ送らない", "C-1 [SHOULD] 丁寧語で答える"):
            self.assertIn(expected, text)
        self.assertIn(f"規範の版: `{self.compiled.digest[:12]}`", text)

    def test_headings_are_nested_under_the_host_section(self):
        sync_file(self.target, self.compiled)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn("\n### 行動規範\n", text)
        self.assertIn("\n#### 理念\n", text)
        self.assertNotIn("\n# 行動規範", text)

    def test_sync_is_idempotent(self):
        sync_file(self.target, self.compiled)
        self.assertFalse(sync_file(self.target, self.compiled))

    def test_check_detects_stale_prompt_without_writing(self):
        sync_file(self.target, self.compiled)
        synced = self.target.read_text(encoding="utf-8")
        (self.root / "30-customs" / "core.md").write_text(
            CUSTOMS + "\n## C-2 結論から書く\n\n- 強度: SHOULD\n- 根拠: P-1\n\n結論を先に書く。\n", encoding="utf-8"
        )
        updated = compile_ethics(self.root)
        self.assertTrue(sync_file(self.target, updated, check=True))
        self.assertEqual(synced, self.target.read_text(encoding="utf-8"))
        # 条文を追記して同期すると、プロンプトに現れる。
        sync_file(self.target, updated)
        self.assertIn("C-2 [SHOULD] 結論から書く", self.target.read_text(encoding="utf-8"))

    def test_markers_are_required(self):
        for text in ("マーカーなし", f"{BEGIN}\n{BEGIN}\n{END}", f"{END}\n{BEGIN}"):
            with self.assertRaises(SyncError):
                sync_text(text, self.compiled)

    def test_cli_check_exit_codes(self):
        args = [str(self.target), "--ethics-dir", str(self.root)]
        self.assertEqual(1, main(["sync", *args, "--check"]))
        self.assertEqual(0, main(["sync", *args]))
        self.assertEqual(0, main(["sync", *args, "--check"]))

    def test_cli_syncs_several_files_with_the_same_block(self):
        agents = self.target.with_name("AGENTS.md")
        agents.write_text(f"# AGENTS\n\n{BEGIN}\n{END}\n", encoding="utf-8")
        args = [str(self.target), str(agents), "--ethics-dir", str(self.root)]
        self.assertEqual(1, main(["sync", *args, "--check"]))
        self.assertEqual(0, main(["sync", *args]))
        self.assertEqual(0, main(["sync", *args, "--check"]))

        def block(path: Path) -> str:
            text = path.read_text(encoding="utf-8")
            return text[text.index(BEGIN) : text.index(END)]

        self.assertEqual(block(self.target), block(agents))
        # 1 つでも同期できないファイルがあれば失敗する。
        self.assertEqual(1, main(["sync", str(self.target), str(agents.with_name("missing.md")), "--ethics-dir", str(self.root)]))


class RepositoryStateTest(unittest.TestCase):
    """このリポジトリ自体の規範と、エージェント向けプロンプトの整合。"""

    def test_agent_prompts_match_ethics(self):
        compiled = compile_ethics(SCAFFOLD)
        targets = [REPO_ROOT / name for name in DEFAULT_TARGETS if (REPO_ROOT / name).exists()]
        if not targets:
            self.skipTest("同期する対象のファイルがありません")
        for target in targets:
            self.assertFalse(
                sync_file(target, compiled, check=True),
                f"{target.name} が ethics/ と一致していません。`python3 -m ethics sync` を実行してください",
            )


class PrGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiled = compile_ethics(SCAFFOLD)

    def ids(self, **event) -> list[str]:
        event.setdefault("body", GOOD_BODY)
        return [v.article_id for v in check_pr(self.compiled, build_event(**event))]

    def test_registered_guards_and_unchecked_rules(self):
        self.assertEqual(["R-4", "R-5"], [a.id for a, _ in self.compiled.guards("pr")])
        self.assertEqual(["R-9"], [a.id for a in unchecked(self.compiled)])

    def test_clean_agent_pr_passes(self):
        self.assertEqual([], self.ids(files=["spec-ai-writer/spec_ai_writer/app.py"], labels=["symphony"], head="symphony/12-fix"))

    def test_pr_body_contract(self):
        self.assertEqual(["R-4"] * 3, self.ids(files=["README.md"], body="本文だけ"))
        self.assertEqual(["R-4"], self.ids(files=["README.md"], body=GOOD_BODY.replace("Fixes #12", "")))

    def test_agent_pr_cannot_touch_protected_paths(self):
        protected = [
            "ethics/00-ideals.md",
            "ethics/10-principles/sdd.md",
            "ethics/20-rules/core.md",
            "ethics/guards/protected_paths.py",
            "ethics/.tools/compiler.py",
            "ethics/__init__.py",
            "ethics/README.md",
            "AGENTS.md",
            "CLAUDE.md",
            "spec-ai-writer/docs/CONSTITUTION.md",
            "WORKFLOW.md",
            ".github/workflows/ci.yml",
        ]
        for path in protected:
            self.assertEqual(["R-5"], self.ids(files=[path], labels=["symphony"]), path)
        # ラベルを外しても、ブランチ名でエージェントの Pull Request と判定する。
        self.assertEqual(["R-5"], self.ids(files=["WORKFLOW.md"], head="symphony/12-fix"))

    def test_agent_may_change_customs(self):
        self.assertEqual([], self.ids(files=["ethics/30-customs/sdd.md"], labels=["symphony"]))

    def test_human_pr_may_amend_rules(self):
        self.assertEqual([], self.ids(files=["ethics/20-rules/sdd.md", "WORKFLOW.md"], labels=[], head="matsuzawa/amend"))

    def test_violation_cites_lineage_to_ideal(self):
        violation = check_pr(self.compiled, build_event(files=["WORKFLOW.md"], body=GOOD_BODY, labels=["symphony"]))[0]
        self.assertIn("P-7", violation.lineage)
        self.assertIn("I-2 人の最終判断を尊重する", violation.lineage)

    def test_report_and_cli_exit_code(self):
        lines, passed = report(self.compiled, build_event(files=["WORKFLOW.md"], body=GOOD_BODY, labels=["symphony"]))
        self.assertFalse(passed)
        self.assertTrue(any("R-5" in line for line in lines))

        with tempfile.TemporaryDirectory() as tmp:
            files = Path(tmp) / "files.txt"
            body = Path(tmp) / "body.md"
            body.write_text(GOOD_BODY, encoding="utf-8")
            base = ["check-pr", str(SCAFFOLD), "--files-from", str(files), "--body-file", str(body)]
            files.write_text("WORKFLOW.md\n", encoding="utf-8")
            self.assertEqual(1, main([*base, "--labels", "symphony"]))
            self.assertEqual(0, main([*base, "--labels", "docs"]))
            files.write_text("README.md\n", encoding="utf-8")
            self.assertEqual(0, main([*base, "--labels", "symphony", "--head", "symphony/12-fix"]))


if __name__ == "__main__":
    unittest.main()
