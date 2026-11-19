"""R-4「Pull Request は根拠となる仕様・仕様差分・Issue を明示する」の決定的ガード。

検査の本体は `.github/scripts/check_pr_body.py` にあり、ここではそれを呼び出す。
適用点 pr の event: {"point": "pr", "body": 本文, "files": [...], "labels": [...], "head": ブランチ名}
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "check_pr_body.py"


def _load_check():
    spec = importlib.util.spec_from_file_location("check_pr_body", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"PR 本文の検査スクリプトを読み込めません: {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.check


def guard(event: dict) -> list[str]:
    return _load_check()(event.get("body") or "")
