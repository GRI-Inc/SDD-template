"""テスト用の最小の倫理階層を一時ディレクトリに作る。"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "ethics"

IDEALS = """\
---
tier: ideal
---
## I-1 信頼を損なわない

預かった情報は利用者のためだけに使う。
"""

PRINCIPLES = """\
---
tier: principle
---
## P-1 個人情報は最小限のみ扱う

- 強度: MUST
- 根拠: I-1
- 検査: judge

必要のない個人情報は扱わない。
"""

RULES = """\
---
tier: rule
---
## R-1 禁止語を外部へ送らない

- 強度: MUST NOT
- 根拠: P-1
- 適用点: tool_call
- 検査: deterministic guards/forbidden.py
- 違反時: block

禁止語を含む内容を送信してはならない。

### 適合例

- 禁止語を含まない内容を送る。

### 違反例

- 禁止語を含む内容を送る。

## R-2 未実行の検証を済んだと報告しない

- 強度: MUST NOT
- 根拠: P-1
- 適用点: output
- 検査: judge
- 違反時: refine
- 例外: 利用者が省略を指示した場合

検証していないことを検証済みと報告してはならない。

### 適合例

- 未実行と報告する。

### 違反例

- 実行せずに通過と報告する。
"""

CUSTOMS = """\
---
tier: custom
---
## C-1 丁寧語で答える

- 強度: SHOULD
- 根拠: P-1
- 検査: judge

返答は丁寧語で書く。
"""

GUARD = """\
def guard(event):
    text = " ".join(str(v) for v in (event.get("args") or {}).values())
    if "CRASH" in text:
        raise RuntimeError("boom")
    return ["禁止語が含まれています"] if "FORBIDDEN" in text else []
"""

FILES = {
    "00-ideals.md": IDEALS,
    "10-principles/core.md": PRINCIPLES,
    "20-rules/core.md": RULES,
    "30-customs/core.md": CUSTOMS,
    "guards/forbidden.py": GUARD,
}


def write_tree(root: Path, overrides: dict | None = None) -> Path:
    """`overrides` でファイルを差し替える。値が None のファイルは作らない。"""
    files = {**FILES, **(overrides or {})}
    for rel, content in files.items():
        if content is None:
            continue
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root
