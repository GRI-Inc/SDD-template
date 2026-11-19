#!/usr/bin/env python3
"""PR 本文が SDD × Issue 駆動開発の契約を満たしているか検査する。

検査項目:
1. `## 関連する仕様` 節に、リポジトリ内の Markdown ファイルへのリンクがある
2. `## 仕様差分` 節が空でない（「変更なし」の明記も可）
3. `## 関連 Issue` 節または本文に `Fixes #N` / `Closes #N` / `Resolves #N` がある

使い方: check_pr_body.py <pr_body.md>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SPEC_HEADING = "## 関連する仕様"
DIFF_HEADING = "## 仕様差分"
ISSUE_HEADING = "## 関連 Issue"

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+\.md(?:#[^)\s]*)?)\)")
ISSUE_REF = re.compile(r"\b(?:Fixes|Closes|Resolves)\s+#\d+", re.IGNORECASE)
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def section(body: str, heading: str) -> str | None:
    """`heading` から次の `## ` 見出しまでの本文を返す。見出しが無ければ None。"""
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end])


def check(body: str) -> list[str]:
    errors: list[str] = []
    body = COMMENT.sub("", body)

    spec = section(body, SPEC_HEADING)
    if spec is None:
        errors.append(f"見出し `{SPEC_HEADING}` がありません")
    else:
        links = MD_LINK.findall(spec)
        if not links:
            errors.append(
                f"`{SPEC_HEADING}` に Markdown ファイルへのリンクがありません"
                "（例: [02-planning-requirement.md](examples/02-planning-requirement.md)）"
            )
        for link in links:
            if link.startswith(("http://", "https://")):
                errors.append(
                    f"`{SPEC_HEADING}` のリンクは相対パスで書いてください: {link}"
                )

    diff = section(body, DIFF_HEADING)
    if diff is None:
        errors.append(f"見出し `{DIFF_HEADING}` がありません")
    elif not diff.strip() or diff.strip() in {"-", "- "}:
        errors.append(
            f"`{DIFF_HEADING}` が空です。仕様を変えていない場合は「変更なし」と書いてください"
        )

    issue = section(body, ISSUE_HEADING)
    target = issue if issue is not None else body
    if not ISSUE_REF.search(target):
        errors.append(
            "`Fixes #N`（または Closes / Resolves）で関連 Issue を指定してください"
        )

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    body = Path(argv[1]).read_text(encoding="utf-8")
    errors = check(body)
    if errors:
        print("PR 本文の検査に失敗しました:")
        for e in errors:
            print(f"  - {e}")
        print("\nテンプレート: .github/pull_request_template.md")
        return 1
    print("PR 本文の検査に合格しました")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
