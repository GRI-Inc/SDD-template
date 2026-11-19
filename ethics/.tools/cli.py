"""倫理階層のコマンドライン。

使い方:
  python3 -m ethics lint [ethics_dir] [--strict] [--tree]
  python3 -m ethics compile [ethics_dir] [--json PATH]
  python3 -m ethics sync [FILE ...] [--check]
  python3 -m ethics check-pr [ethics_dir] --files-from PATH [--body-file PATH] [--labels a,b] [--head BRANCH]
  python3 -m ethics test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compiler import EthicsCompileError, compile_ethics
from .prcheck import build_event, report
from .spec import TIER_LABEL, TIERS, format_tree, lint
from .sync import DEFAULT_TARGETS, SyncError, sync_file


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
    for point in ("input", "plan", "tool_call", "output", "pr"):
        guards = ", ".join(a.id for a, _ in compiled.guards(point)) or "なし"
        judged = ", ".join(a.id for a in compiled.judged(point)) or "なし"
        print(f"{point}: ガード [{guards}] / 判定器 [{judged}]")
    return 0


def run_sync(args: argparse.Namespace) -> int:
    # 対象を省略したときは、既定のファイルのうち存在するものを同期する。
    targets = args.targets or [t for t in DEFAULT_TARGETS if Path(t).exists()]
    if not targets:
        print(f"同期する対象がありません（既定: {', '.join(DEFAULT_TARGETS)}）", file=sys.stderr)
        return 1

    try:
        compiled = compile_ethics(args.ethics_dir)
    except EthicsCompileError as err:
        print(err, file=sys.stderr)
        return 1

    stale = []
    for target in targets:
        try:
            changed = sync_file(target, compiled, check=args.check)
        except (SyncError, OSError) as err:
            print(f"{target}: {err}", file=sys.stderr)
            return 1
        if args.check and changed:
            stale.append(target)
            continue
        state = "更新しました" if changed else "最新です"
        print(f"{target}: {state}（規範の版 {compiled.digest[:12]}）")

    if stale:
        print(f"行動規範が ethics/ と一致していません: {', '.join(stale)}")
        print("次を実行してください:")
        print("  python3 -m ethics sync")
        return 1
    return 0


def run_check_pr(args: argparse.Namespace) -> int:
    try:
        compiled = compile_ethics(args.ethics_dir)
        files = [line.strip() for line in Path(args.files_from).read_text(encoding="utf-8").splitlines() if line.strip()]
        body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else ""
    except (EthicsCompileError, OSError) as err:
        print(err, file=sys.stderr)
        return 1

    labels = [label.strip() for label in args.labels.split(",") if label.strip()]
    lines, passed = report(compiled, build_event(files, body, labels, args.head, args.title))
    print("\n".join(lines))
    return 0 if passed else 1


def run_test(args: argparse.Namespace) -> int:
    """道具自身のテストを実行する。

    `.tools/` はドットで始まるので、unittest の探索（パスからモジュール名を作る）では
    辿れない。`ethics.tests` 配下のモジュールを名前で読み込んで実行する。
    """
    import importlib
    import pkgutil
    import unittest

    package = importlib.import_module("ethics.tests")
    names = sorted(f"ethics.tests.{m.name}" for m in pkgutil.iter_modules(package.__path__) if m.name.startswith("test_"))
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(buffer=True, verbosity=2 if args.verbose else 1).run(suite)
    return 0 if result.wasSuccessful() else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ethics", description="倫理階層（ethics/）の検査とコンパイル")
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

    p_sync = sub.add_parser("sync", help="エージェント向けプロンプトのファイルへ条文集を書き込む")
    p_sync.add_argument("targets", nargs="*", help=f"同期するファイル（省略時: {' と '.join(DEFAULT_TARGETS)}）")
    p_sync.add_argument("--ethics-dir", default="ethics")
    p_sync.add_argument("--check", action="store_true", help="書き込まず、同期漏れがあれば失敗する")
    p_sync.set_defaults(func=run_sync)

    p_pr = sub.add_parser("check-pr", help="Pull Request に適用点 pr の決定的ガードを実行する")
    p_pr.add_argument("ethics_dir", nargs="?", default="ethics")
    p_pr.add_argument("--files-from", required=True, metavar="PATH", help="変更されたパスを 1 行ずつ書いたファイル")
    p_pr.add_argument("--body-file", metavar="PATH", help="Pull Request の本文を書いたファイル")
    p_pr.add_argument("--labels", default="", help="ラベルをカンマ区切りで")
    p_pr.add_argument("--head", default="", help="Pull Request のブランチ名")
    p_pr.add_argument("--title", default="")
    p_pr.set_defaults(func=run_check_pr)

    p_test = sub.add_parser("test", help="道具自身のテストを実行する")
    p_test.add_argument("-v", "--verbose", action="store_true")
    p_test.set_defaults(func=run_test)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
