from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ethic_layer import compile_ethics
from ethic_layer.tests.fixtures import write_tree

try:
    import dspy
    from dspy.utils import DummyLM
except ImportError:  # DSPy が無い環境では、このファイルのテストを飛ばす
    dspy = None

if dspy is not None:
    from ethic_layer.dspy_adapter import (
        EthicsViolation,
        Governed,
        Judge,
        guard_tool,
        guard_tools,
        make_metric,
        with_ethics,
    )


def tool_call(name: str, args: dict) -> str:
    return json.dumps({"tool_calls": [{"name": name, "args": args}]})


def exact_match(gold, pred, trace=None):
    return float(gold.answer == pred.answer)


@unittest.skipIf(dspy is None, "DSPy が入っていません")
class DspyAdapterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.compiled = compile_ethics(write_tree(Path(self._tmp.name)))
        self.sent: list[str] = []

        def send(body: str) -> str:
            """内容を外部へ送信する。"""
            self.sent.append(body)
            return "sent"

        self.send = send
        self.gold = dspy.Example(question="q", answer="42").with_inputs("question")

    def configure(self, answers):
        lm = DummyLM(answers)
        dspy.configure(lm=lm)
        return lm

    # --- 条文集の注入 ---

    def test_with_ethics_adds_frozen_field_and_optimizable_customs(self):
        sig = with_ethics("question -> answer", self.compiled)
        self.assertEqual(["ethics", "question"], list(sig.input_fields))
        self.assertIn("丁寧語で答える", sig.instructions)
        self.assertNotIn("禁止語を含む内容を送信してはならない", sig.instructions)

    def test_governed_passes_frozen_prompt_as_input_value(self):
        lm = self.configure([{"answer": "42"}])
        program = Governed(dspy.Predict(with_ethics("question -> answer", self.compiled)), self.compiled)
        pred = program(question="q")
        prompt = json.dumps(lm.history[-1]["messages"], ensure_ascii=False, default=str)
        self.assertIn("禁止語を含む内容を送信してはならない", prompt)
        self.assertEqual("42", pred.answer)
        self.assertEqual(self.compiled.digest, pred.ethics_digest)
        self.assertEqual([], pred.ethics_log)

    def test_governed_survives_deepcopy(self):
        program = Governed(dspy.Predict(with_ethics("question -> answer", self.compiled)), self.compiled)
        self.assertEqual(self.compiled.digest, program.deepcopy().compiled.digest)

    # --- ツールガード ---

    def test_guard_tool_keeps_schema_and_passes_clean_calls(self):
        tool = guard_tool(self.send, self.compiled)
        self.assertEqual(("send", {"body": {"type": "string"}}), (tool.name, tool.args))
        self.assertEqual("sent", tool(body="hello"))
        self.assertEqual(["hello"], self.sent)

    def test_guard_tool_blocks_violation_before_execution(self):
        tool = guard_tool(self.send, self.compiled)
        with self.assertRaises(EthicsViolation) as ctx:
            tool(body="FORBIDDEN data")
        self.assertEqual(["R-1"], [v.article_id for v in ctx.exception.violations])
        self.assertEqual([], self.sent)

    def test_react_agent_is_blocked_and_told_why(self):
        lm = self.configure(
            [
                {"next_thought": "送る", "tool_calls": tool_call("send", {"body": "FORBIDDEN data"})},
                {"next_thought": "やめる", "tool_calls": tool_call("submit", {"answer": "42"})},
            ]
        )
        signature = with_ethics(dspy.Signature("question -> answer", "質問に答える。"), self.compiled)
        agent = Governed(dspy.ReAct(signature, tools=guard_tools([self.send], self.compiled)), self.compiled)
        pred = agent(question="q")

        self.assertEqual([], self.sent)
        self.assertEqual("42", pred.answer)
        self.assertEqual([("send", True)], [(e["tool"], e["blocked"]) for e in pred.ethics_log])
        second_prompt = json.dumps(lm.history[-1]["messages"], ensure_ascii=False, default=str)
        self.assertIn("規範に違反するため実行しません", second_prompt)

        # 阻止された試みも違反として数え、タスクが正解でもスコアは 0 になる。
        result = make_metric(self.compiled, exact_match)(self.gold, pred)
        self.assertEqual(0.0, float(result))
        self.assertIn("R-1 禁止語を外部へ送らない", result.feedback)
        self.assertIn("← I-1 信頼を損なわない", result.feedback)

    # --- metric ゲート ---

    def test_metric_uses_task_score_when_compliant(self):
        metric = make_metric(self.compiled, exact_match)
        right = metric(self.gold, dspy.Prediction(answer="42"))
        wrong = metric(self.gold, dspy.Prediction(answer="0"))
        self.assertEqual((1.0, 0.0), (float(right), float(wrong)))
        self.assertIn("違反はありません", right.feedback)

    def test_metric_keeps_task_feedback(self):
        task = lambda gold, pred, trace=None: dspy.Prediction(score=0.5, feedback="半分だけ合っている")  # noqa: E731
        result = make_metric(self.compiled, task)(self.gold, dspy.Prediction(answer="42"))
        self.assertEqual(0.5, float(result))
        self.assertIn("半分だけ合っている", result.feedback)

    def test_judge_violation_of_rule_zeroes_score(self):
        self.configure(
            {
                "規則 R-2": {"violated": "True", "reason": "テスト未実行なのに通過と報告"},
                "原則 P-1": {"violated": "False", "reason": "問題なし"},
                "慣習 C-1": {"violated": "False", "reason": "問題なし"},
            }
        )
        metric = make_metric(self.compiled, exact_match, judge=Judge())
        result = metric(self.gold, dspy.Prediction(answer="42"))
        self.assertEqual(0.0, float(result))
        self.assertIn("R-2", result.feedback)
        self.assertIn("テスト未実行なのに通過と報告", result.feedback)

    def test_custom_violation_only_reduces_score(self):
        # DummyLM は先に一致したキーを使う。下位の条文は系譜に上位の条文名を含むので、下位を先に並べる。
        self.configure(
            {
                "慣習 C-1": {"violated": "True", "reason": "丁寧語ではない"},
                "規則 R-2": {"violated": "False", "reason": "問題なし"},
                "原則 P-1": {"violated": "False", "reason": "問題なし"},
            }
        )
        metric = make_metric(self.compiled, exact_match, judge=Judge(), custom_penalty=0.25)
        result = metric(self.gold, dspy.Prediction(answer="42"))
        self.assertEqual(0.75, float(result))
        self.assertIn("慣習からの逸脱", result.feedback)

    def test_float_mode_is_falsy_on_violation(self):
        pred = dspy.Prediction(answer="42")
        pred.ethics_log = [
            {
                "tool": "send",
                "args": {},
                "blocked": True,
                "violations": [self.compiled.violation("R-1", "tool_call", "x", "guard")],
            }
        ]
        pred.ethics_digest = self.compiled.digest
        with_feedback = make_metric(self.compiled, exact_match)(self.gold, pred, [])
        as_float = make_metric(self.compiled, exact_match, feedback=False)(self.gold, pred, [])
        self.assertTrue(bool(with_feedback))  # Prediction はスコア 0 でも真。float 版が必要な理由
        self.assertIs(type(as_float), float)
        self.assertFalse(as_float)

    def test_metric_works_with_evaluate(self):
        self.configure([{"answer": "42"}, {"answer": "0"}])
        program = Governed(dspy.Predict(with_ethics("question -> answer", self.compiled)), self.compiled)
        evaluate = dspy.Evaluate(devset=[self.gold, self.gold], metric=make_metric(self.compiled, exact_match), num_threads=1)
        self.assertEqual(50.0, evaluate(program).score)


if __name__ == "__main__":
    unittest.main()
