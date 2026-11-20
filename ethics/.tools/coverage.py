"""網羅の報告: 条文ごとに、DSPy の経路でどの保証の水準で扱われるかを示す。

水準:
  強制   違反する操作は実行されない（決定的ガード）
  検出   違反を実行時に見つけて対処する（実行時の判定器）
  測定   評価データの上で違反を数える。個々の実行は止めない
  対象外 DSPy の経路では扱わない

水準は接続の設定で変わるので、設定を受け取って報告する。水準を実際より高く見せないことが目的。
実行時の判定器はまだ無いため、現在は「検出」になる条文は無い。標準ライブラリだけで動く。
"""

from __future__ import annotations

from dataclasses import dataclass

from .compiler import Compiled, CompiledArticle
from .spec import TIER_LABEL, TIERS

ENFORCED = "強制"
DETECTED = "検出"
MEASURED = "測定"
UNCOVERED = "対象外"
LEVELS = (ENFORCED, DETECTED, MEASURED, UNCOVERED)

# DSPy の経路で検査する適用点。`plan` と `pr` は扱わない。
DSPY_POINTS = ("input", "tool_call", "output")
DEFAULT_POINT = "output"


@dataclass(frozen=True)
class CoverageRow:
    id: str
    title: str
    tier: str
    level: str
    reason: str

    @property
    def label(self) -> str:
        return TIER_LABEL[self.tier]


def _level(a: CompiledArticle, judge: bool) -> tuple[str, str]:
    if a.tier == "ideal":
        if judge:
            return MEASURED, "支配構造の評価の中でだけ判定する。実行時と metric では判定しない"
        return UNCOVERED, "理念は直接検査しない。判定器が無い設定では、評価でも判定しない"

    if not a.check:
        return UNCOVERED, "`検査` を持たないため、判定しない"

    points = a.points or (DEFAULT_POINT,)
    covered = [p for p in points if p in DSPY_POINTS]
    if not covered:
        if "pr" in points and a.check == "deterministic":
            return UNCOVERED, "適用点 pr は CI（ethics check-pr）が検査する"
        if "pr" in points:
            return UNCOVERED, "適用点 pr の判定器条文は、人間のレビューが確認する"
        return UNCOVERED, "適用点 plan は、計画の表現が決まっていないため検査できない"
    where = ", ".join(covered)

    if a.check == "deterministic":
        stops_output = a.tier != "custom" and a.on_violation in ("", "block")
        if "input" in covered or "tool_call" in covered or stops_output:
            return ENFORCED, f"決定的ガードが実行の前に止める（{where}）"
        if a.tier == "custom":
            return MEASURED, "決定的ガードが違反を記録する。慣習の違反では止めない"
        return MEASURED, f"決定的ガードが違反を記録する。`違反時: {a.on_violation}` は未実装のため止めない"

    if judge:
        return MEASURED, f"metric の中で、実行の後に判定器が判定する（{where}）"
    return UNCOVERED, "判定器を渡さない設定では判定しない"


def coverage(compiled: Compiled, judge: bool = False) -> list[CoverageRow]:
    """条文ごとの保証の水準を、層の順に返す。`judge` は、評価に判定器を使う設定かどうか。"""
    rows: list[CoverageRow] = []
    for tier in TIERS:
        for a in compiled.by_tier(tier):
            level, reason = _level(a, judge)
            rows.append(CoverageRow(a.id, a.title, a.tier, level, reason))
    return rows


def summarize(rows: list[CoverageRow]) -> dict[str, int]:
    return {level: sum(1 for r in rows if r.level == level) for level in LEVELS}


def render(rows: list[CoverageRow], judge: bool) -> str:
    """報告を、人が読むテキストにする。"""
    lines = [f"設定: 判定器{'あり' if judge else 'なし'}"]
    for level in LEVELS:
        items = [r for r in rows if r.level == level]
        lines.append("")
        lines.append(f"## {level}（{len(items)} 件）")
        lines.extend(f"- [{r.label}] {r.id} {r.title}: {r.reason}" for r in items)
        if not items:
            lines.append("- なし")
    counts = "、".join(f"{level} {count}" for level, count in summarize(rows).items())
    lines.append("")
    lines.append(f"条文 {len(rows)} 件: {counts}")
    return "\n".join(lines)
