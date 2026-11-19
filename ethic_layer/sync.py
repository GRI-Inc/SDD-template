"""コンパイルした条文集を、エージェント向けプロンプトのファイルへ書き込む。

対象ファイルの `<!-- ethics:begin -->` と `<!-- ethics:end -->` の間を、条文集で置き換える。
条文を追記したらこの同期を実行する。CI は `--check` で、同期漏れを検出する。
"""

from __future__ import annotations

import re
from pathlib import Path

from .compiler import Compiled

BEGIN = "<!-- ethics:begin -->"
END = "<!-- ethics:end -->"
NOTICE = "<!-- この区間は `python3 -m ethic_layer sync` が ethics/ から生成します。手で編集しないでください。 -->"


class SyncError(Exception):
    pass


def render_block(compiled: Compiled, heading_offset: int = 2) -> str:
    """マーカーを含む区間全体を返す。見出しは `heading_offset` 段だけ下げて埋め込む。"""
    body = re.sub(r"^(#+ )", lambda m: "#" * heading_offset + m.group(1), compiled.agent_prompt(), flags=re.MULTILINE)
    return "\n".join([BEGIN, NOTICE, "", body, "", f"規範の版: `{compiled.digest[:12]}`", END])


def sync_text(text: str, compiled: Compiled, heading_offset: int = 2) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(BEGIN) > text.index(END):
        raise SyncError(f"`{BEGIN}` と `{END}` を、この順で 1 組だけ置いてください")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    return head + render_block(compiled, heading_offset) + tail


def sync_file(path: str | Path, compiled: Compiled, check: bool = False) -> bool:
    """ファイルを同期する。内容が変わる（変わった）なら True。`check=True` のときは書き込まない。"""
    path = Path(path)
    current = path.read_text(encoding="utf-8")
    updated = sync_text(current, compiled)
    if updated == current:
        return False
    if not check:
        path.write_text(updated, encoding="utf-8")
    return True
