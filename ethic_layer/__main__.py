"""倫理階層のコマンドライン。

使い方:
  python3 -m ethic_layer lint [ethics_dir] [--strict] [--tree]
  python3 -m ethic_layer compile [ethics_dir] [--json PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compiler import EthicsCompileError, compile_ethics
from .spec import TIER_LABEL, TIERS, format_tree, lint


def run_lint(args: argparse.Namespace) -> int:
    root = Path(args.ethics_dir)
    if not root.is_dir():
        print(f"ディレクトリがありません: {root}", file=sys.stderr)
        return 2

    articles, findings = lint(root)
    if args.tree:
        print(format_tree(articles))
        print()
    for f in findings:
        print(f)

    errors = sum(1 for f in findings if f.is_error)
    warnings = len(findings) - errors
    counts = "、".join(f"{TIER_LABEL[t]} {sum(1 for a in articles if a.tier == t)}" for t in TIERS)
    print(f"条文: {counts} / エラー {errors}、警告 {warnings}")

    if errors or (args.strict and warnings):
        print("倫理階層の検査に失敗しました")
        return 1
    print("倫理階層の検査に合格しました")
    return 0


def run_compile(args: argparse.Namespace) -> int:
    try:
        compiled = compile_ethics(args.ethics_dir)
    except EthicsCompileError as err:
        print(err, file=sys.stderr)
        return 1

    if args.json:
        Path(args.json).write_text(compiled.to_json() + "\n", encoding="utf-8")
        print(f"書き出しました: {args.json}（digest {compiled.digest[:12]}）")
        return 0

    print(compiled.prompt())
    customs = compiled.customs_prompt()
    if customs:
        print("\n---- 慣習（最適化してよい指示文の初期値） ----\n")
        print(customs)
    print(f"\n---- digest {compiled.digest[:12]} ----")
    for point in ("input", "plan", "tool_call", "output"):
        guards = ", ".join(a.id for a, _ in compiled.guards(point)) or "なし"
        judged = ", ".join(a.id for a in compiled.judged(point)) or "なし"
        print(f"{point}: ガード [{guards}] / 判定器 [{judged}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ethic_layer", description="倫理階層（ethics/）の検査とコンパイル")
    sub = parser.add_subparsers(dest="command", required=True)

    p_lint = sub.add_parser("lint", help="条文の構造を検査する")
    p_lint.add_argument("ethics_dir", nargs="?", default="ethics")
    p_lint.add_argument("--strict", action="store_true", help="警告もエラーとして扱う")
    p_lint.add_argument("--tree", action="store_true", help="根拠のつながりを木で表示する")
    p_lint.set_defaults(func=run_lint)

    p_compile = sub.add_parser("compile", help="条文集プロンプトと登録表を出力する")
    p_compile.add_argument("ethics_dir", nargs="?", default="ethics")
    p_compile.add_argument("--json", metavar="PATH", help="登録表を JSON で書き出す")
    p_compile.set_defaults(func=run_compile)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
