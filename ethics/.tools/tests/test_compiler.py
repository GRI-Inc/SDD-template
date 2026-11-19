from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ethics import EthicsCompileError, compile_ethics
from ethics.tests.fixtures import PRINCIPLES, RULES, SCAFFOLD, write_tree


class CompilerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = write_tree(Path(self._tmp.name))
        self.compiled = compile_ethics(self.root)

    def test_refuses_to_compile_when_lint_fails(self):
        (self.root / "10-principles" / "core.md").write_text(
            PRINCIPLES.replace("根拠: I-1", "根拠: I-9"), encoding="utf-8"
        )
        with self.assertRaises(EthicsCompileError) as ctx:
            compile_ethics(self.root)
        self.assertEqual(["E009"], [f.code for f in ctx.exception.findings])

    def test_refuses_guard_without_guard_function(self):
        (self.root / "guards" / "forbidden.py").write_text("def check():\n    return []\n", encoding="utf-8")
        with self.assertRaises(EthicsCompileError):
            compile_ethics(self.root)

    def test_frozen_prompt_orders_tiers_and_excludes_customs(self):
        prompt = self.compiled.prompt()
        self.assertLess(prompt.index("## 理念"), prompt.index("## 原則"))
        self.assertLess(prompt.index("## 原則"), prompt.index("## 規則"))
        self.assertIn("- R-1 [MUST NOT] 禁止語を外部へ送らない（根拠: P-1）", prompt)
        self.assertIn("例外: 利用者が省略を指示した場合", prompt)
        self.assertNotIn("丁寧語", prompt)

    def test_customs_prompt_holds_only_customs(self):
        customs = self.compiled.customs_prompt()
        self.assertIn("C-1 [SHOULD] 丁寧語で答える", customs)
        self.assertNotIn("禁止語", customs)

    def test_lineage_reaches_ideal(self):
        self.assertEqual(["R-1", "P-1", "I-1"], [a.id for a in self.compiled.lineage("R-1")])
        self.assertIn("← I-1 信頼を損なわない", self.compiled.lineage_text("R-1"))

    def test_guard_registry_by_point(self):
        self.assertEqual(["R-1"], [a.id for a, _ in self.compiled.guards("tool_call")])
        self.assertEqual([], self.compiled.guards("output"))

    def test_judged_articles_by_point(self):
        self.assertEqual(["P-1", "R-2", "C-1"], [a.id for a in self.compiled.judged("output")])
        self.assertEqual([], self.compiled.judged("tool_call"))

    def test_check_guards_reports_violation_with_lineage(self):
        ok = self.compiled.check_guards("tool_call", {"tool": "send", "args": {"body": "hello"}})
        self.assertEqual([], ok)
        bad = self.compiled.check_guards("tool_call", {"tool": "send", "args": {"body": "FORBIDDEN"}})
        self.assertEqual(1, len(bad))
        self.assertEqual(("R-1", "block", "guard", True), (bad[0].article_id, bad[0].on_violation, bad[0].source, bad[0].hard))
        self.assertIn("I-1", bad[0].lineage)

    def test_guard_exception_fails_closed(self):
        bad = self.compiled.check_guards("tool_call", {"tool": "send", "args": {"body": "CRASH"}})
        self.assertEqual(1, len(bad))
        self.assertIn("安全側", bad[0].reason)

    def test_article_text_for_judge(self):
        text = self.compiled.article_text("R-2")
        for expected in ("規則 R-2", "例外", "原則 P-1", "理念 I-1", "適合例", "実行せずに通過と報告する。"):
            self.assertIn(expected, text)

    def test_digest_tracks_content(self):
        before = self.compiled.digest
        self.assertEqual(before, compile_ethics(self.root).digest)
        (self.root / "20-rules" / "core.md").write_text(RULES.replace("送信してはならない", "送ってはならない"), encoding="utf-8")
        self.assertNotEqual(before, compile_ethics(self.root).digest)

    def test_json_export(self):
        data = json.loads(self.compiled.to_json())
        self.assertEqual(self.compiled.digest, data["digest"])
        self.assertEqual(["I-1", "P-1", "R-1", "R-2", "C-1"], [a["id"] for a in data["articles"]])

    def test_scaffold_compiles_and_blocks_pii_egress(self):
        compiled = compile_ethics(SCAFFOLD)
        self.assertEqual([], compiled.warnings)
        external = {"tool": "http_post", "args": {"url": "https://api.example.com/t", "body": "taro@example.com"}}
        internal = {"tool": "http_post", "args": {"url": "https://crm.example.internal/t", "body": "taro@example.com"}}
        self.assertEqual(["R-1"], [v.article_id for v in compiled.check_guards("tool_call", external)])
        self.assertEqual([], compiled.check_guards("tool_call", internal))


if __name__ == "__main__":
    unittest.main()
