"""R-5「エージェントの Pull Request で規範と執行の仕組みを変更しない」の決定的ガード。

エージェントの Pull Request かどうかは、`symphony` ラベル、または `symphony/` で始まるブランチ名で判定する。
適用点 pr の event: {"point": "pr", "files": [変更されたパス], "labels": [...], "head": ブランチ名, "body": 本文}
"""

from __future__ import annotations

AGENT_LABEL = "symphony"
AGENT_BRANCH_PREFIX = "symphony/"

# 末尾が `/` のものは、その配下すべてを指す。
# `ethics/` は条文・ガード・条文を適用する道具（.tools）をまとめて持つので、全体を保護する。
PROTECTED = (
    "ethics/",
    "WORKFLOW.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".github/workflows/",
    ".github/scripts/",
)

# 保護対象の中で、エージェントが変更してよいもの。慣習はチームの裁量で改正できる層。
ALLOWED = ("ethics/30-customs/",)


def is_agent_pr(event: dict) -> bool:
    return AGENT_LABEL in (event.get("labels") or []) or str(event.get("head") or "").startswith(AGENT_BRANCH_PREFIX)


def _matches(path: str, patterns: tuple) -> bool:
    return any(path == p or (p.endswith("/") and path.startswith(p)) for p in patterns)


def is_protected(path: str) -> bool:
    return _matches(path, PROTECTED) and not _matches(path, ALLOWED)


def guard(event: dict) -> list[str]:
    if not is_agent_pr(event):
        return []
    return [f"エージェントの Pull Request が保護対象を変更しています: {f}" for f in (event.get("files") or []) if is_protected(f)]
