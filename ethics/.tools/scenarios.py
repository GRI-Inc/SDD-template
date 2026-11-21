"""検証セット（ethics/evals/）の場面を読み込み、検査する。

検証セットは、支配構造が効いているかを確かめるための、人間が正解を定めた場面の集まり。
条文と同じ書き方をする。

    ## S-1 題名

    - 種類: 衝突
    - 条文: R-1, C-3

    ### 入力

    プログラムに渡す依頼。

    ### 正解

    正しい振る舞いの説明。

種類は 衝突 / 欠缺 / 例外 / 通常 のいずれか。`条文` は関係する条文の ID で、通常の場面では省略できる。
標準ライブラリだけで動く。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .spec import EVALS_DIR, Article, Finding, parse_file, parse_frontmatter, split_list

SCENARIO_PREFIX = "S"
KINDS = ("衝突", "欠缺", "例外", "通常")
# 関係する条文を書かなくてよい種類。規範に関わらない依頼なので、関係する条文が無い。
KINDS_WITHOUT_ARTICLES = ("通常",)
FIELDS = ("種類", "条文")
INPUT_SECTION = "入力"
EXPECTED_SECTION = "正解"


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    kind: str
    articles: tuple
    input: str
    expected: str
    path: Path
    line: int


def _section(a: Article, name: str) -> str:
    return "\n".join(a.sections.get(name, [])).strip()


def _to_scenario(a: Article) -> Scenario:
    return Scenario(
        id=a.id,
        title=a.title,
        kind=a.get("種類"),
        articles=tuple(split_list(a.get("条文"))),
        input=_section(a, INPUT_SECTION),
        expected=_section(a, EXPECTED_SECTION),
        path=a.path,
        line=a.line,
    )


def _parse(root: Path, findings: list[Finding]) -> list[Article]:
    directory = root / EVALS_DIR
    if not directory.is_dir():
        return []
    parsed: list[Article] = []
    for path in sorted(directory.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        _, start = parse_frontmatter(lines)
        parsed.extend(parse_file(path, "scenario", start, lines, findings))
    return parsed


def lint_scenarios(root: Path, article_ids: set[str]) -> tuple[list[Scenario], list[Finding]]:
    """場面と検査結果を返す。`article_ids` は、定義済みの条文の ID。"""
    findings: list[Finding] = []
    seen: dict[str, Article] = {}

    parsed = _parse(root, findings)
    for a in parsed:

        def add(code: str, message: str, line: int | None = None, a: Article = a) -> None:
            findings.append(Finding(a.path, line or a.line, code, f"{a.id}: {message}"))

        if not a.id.startswith(f"{SCENARIO_PREFIX}-"):
            add("E014", f"場面の ID は {SCENARIO_PREFIX}- で始めてください")
        if a.id in seen:
            first = seen[a.id]
            add("E014", f"場面の ID が重複しています（先の定義: {first.path}:{first.line}）")
        else:
            seen[a.id] = a

        for name, (_, line) in a.fields.items():
            if name not in FIELDS:
                add("E014", f"場面では `{name}` を使えません（{' / '.join(FIELDS)}）", line)

        kind = a.get("種類")
        if not kind:
            add("E014", "必須フィールド `種類` がありません")
        elif kind not in KINDS:
            add("E014", f"`種類` は {' / '.join(KINDS)} のいずれかです（現在: {kind}）", a.fields["種類"][1])

        refs = split_list(a.get("条文"))
        if not refs and kind in KINDS and kind not in KINDS_WITHOUT_ARTICLES:
            add("E014", f"種類が {kind} の場面には、関係する条文を `条文` に書いてください")
        for ref in refs:
            if ref not in article_ids:
                add("E015", f"条文 {ref} は定義されていません", a.fields["条文"][1])

        for name in (INPUT_SECTION, EXPECTED_SECTION):
            if not _section(a, name):
                add("E014", f"`### {name}` がありません、または空です")

    findings.sort(key=lambda f: (str(f.path), f.line, f.code))
    return [_to_scenario(a) for a in parsed], findings


def load_scenarios(root: str | Path = "ethics") -> list[Scenario]:
    """検証セットの場面を読み込む。書式の検査はしない（`lint` が行う）。"""
    return [_to_scenario(a) for a in _parse(Path(root), [])]
