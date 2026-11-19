"""Pull Request に対して、適用点 pr の決定的ガードを実行する。

条文に `適用点: pr` と `検査: deterministic <ガード>` を書けば、CI の定義を変えずに検査が増える。
`検査: judge` の条文は、ここでは検査しない（一覧として表示するだけ）。
"""

from __future__ import annotations

from .compiler import Compiled, CompiledArticle, Violation

POINT = "pr"


def build_event(files: list[str], body: str = "", labels: list[str] | None = None, head: str = "", title: str = "") -> dict:
    return {"files": files, "body": body, "labels": labels or [], "head": head, "title": title}


def check_pr(compiled: Compiled, event: dict) -> list[Violation]:
    return compiled.check_guards(POINT, event)


def unchecked(compiled: Compiled) -> list[CompiledArticle]:
    """適用点 pr を持つが、自動では検査されない条文。"""
    return compiled.judged(POINT)


def report(compiled: Compiled, event: dict) -> tuple[list[str], bool]:
    """表示する行と、合格したかどうかを返す。"""
    violations = check_pr(compiled, event)
    checked = ", ".join(a.id for a, _ in compiled.guards(POINT)) or "なし"
    lines = [f"規範の版: {compiled.digest[:12]}", f"検査した条文: {checked}"]
    pending = unchecked(compiled)
    if pending:
        lines.append("自動では検査しない条文（レビューで確認）: " + ", ".join(a.id for a in pending))
    if violations:
        lines.append("")
        lines.append("規範に違反しています:")
        lines.extend(f"  - {v.render()}" for v in violations)
    else:
        lines.append("適用点 pr の決定的ガードに合格しました")
    return lines, not violations
