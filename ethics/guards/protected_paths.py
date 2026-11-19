"""R-5「エージェントの Pull Request で規範・憲章・執行の仕組みを変更しない」の決定的ガード。

エージェントの Pull Request かどうかは、`symphony` ラベル、または `symphony/` で始まるブランチ名で判定する。
適用点 pr の event: {"point": "pr", "files": [変更されたパス], "labels": [...], "head": ブランチ名, "body": 本文}
"""

from __future__ import annotations

AGENT_LABEL = "symphony"
AGENT_BRANCH_PREFIX = "symphony/"

# 末尾が `/` のものは、その配下すべてを指す。慣習（ethics/30-customs/）は含めない。
PROTECTED = (
    "ethics/00-ideals.md",
    "ethics/10-principles/",
    "ethics/20-rules/",
    "ethics/guards/",
    "ethic_layer/",
    "spec-ai-writer/docs/CONSTITUTION.md",
    "WORKFLOW.md",
    ".github/workflows/",
    ".github/scripts/",
)


def is_agent_pr(event: dict) -> bool:
    return AGENT_LABEL in (event.get("labels") or []) or str(event.get("head") or "").startswith(AGENT_BRANCH_PREFIX)


def is_protected(path: str) -> bool:
    return any(path == p or (p.endswith("/") and path.startswith(p)) for p in PROTECTED)


def guard(event: dict) -> list[str]:
    if not is_agent_pr(event):
        return []
    return [f"エージェントの Pull Request が保護対象を変更しています: {f}" for f in (event.get("files") or []) if is_protected(f)]
