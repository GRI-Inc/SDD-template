#!/usr/bin/env python3
"""ethics/ 配下の条文が、倫理階層の支配構造を保っているか検査する。

検査の本体は `ethic_layer/spec.py` にあり、エラーコードの一覧もそちらに記載している。
`python3 -m ethic_layer lint` と同じ動作をする。

使い方: lint_ethics.py [ethics_dir] [--strict] [--tree]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ethic_layer.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["lint", *sys.argv[1:]]))
