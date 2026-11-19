"""R-1「個人情報を組織外の宛先へ送信しない」の決定的ガード（雛形）。

ガードの契約: モジュールに `guard(event: dict) -> list[str]` を定義する。
違反の説明を返し、空リストなら適合。適用点 tool_call では次の event を受け取る。

    {"point": "tool_call", "tool": "<ツール名>", "args": {<引数名>: <値>}}

検出パターン・組織内ドメイン・宛先とみなす引数名は、導入先に合わせて置き換えること。
"""

from __future__ import annotations

import re

# 組織内とみなす宛先のドメイン。導入先に合わせて書き換える。
INTERNAL_DOMAINS = ("example.internal",)

# ツールの引数のうち、宛先とみなす引数名。
DESTINATION_KEYS = ("url", "to", "destination", "endpoint")

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\b0\d{1,4}-\d{1,4}-\d{3,4}\b")


def is_internal(destination: str) -> bool:
    host = re.sub(r"^[a-z]+://", "", destination).split("/")[0].split("@")[-1]
    return any(host == d or host.endswith("." + d) for d in INTERNAL_DOMAINS)


def check(destination: str, payload: str) -> list[str]:
    if is_internal(destination):
        return []
    violations = []
    if EMAIL.search(payload):
        violations.append(f"メールアドレスを組織外 ({destination}) へ送信しようとしています")
    if PHONE.search(payload):
        violations.append(f"電話番号を組織外 ({destination}) へ送信しようとしています")
    return violations


def guard(event: dict) -> list[str]:
    """宛先の引数を持つツール呼び出しについて、宛先以外の引数に個人情報が含まれないか調べる。"""
    args = event.get("args") or {}
    destination = next((str(args[k]) for k in DESTINATION_KEYS if args.get(k)), None)
    if destination is None:
        return []
    payload = "\n".join(str(v) for k, v in args.items() if k not in DESTINATION_KEYS)
    return check(destination, payload)
