"""倫理階層（ethics/）の条文を読み込み、支配構造を検査する。

階層（上が強い）: 理念 ideal > 原則 principle > 規則 rule > 慣習 custom

エラー:
  E001 frontmatter の tier が無い、または不正
  E002 ファイルの置き場所と tier が一致しない
  E003 `## ` 見出しが条文 ID 形式（例: `## R-1 題名`）でない
  E004 ID の接頭辞が tier と一致しない
  E005 ID が重複している
  E006 必須フィールドが無い
  E007 その層で使えない、または未知のフィールドがある
  E008 フィールドの値が不正
  E009 根拠が未定義の ID を指している
  E010 根拠が上位層の条文でない
  E011 deterministic と宣言したガードのファイルが無い
  E012 条文の本文が無い
  E013 条文が 1 つも無い

警告:
  W001 理念を具体化する規則が 1 つも無い（執行手段が無い）
  W002 理念が 7 個を超えている
  W003 規則に `### 適合例` または `### 違反例` が無い

下位条文が上位条文を「緩めて」いないかという意味の検査は行わない。
標準ライブラリだけで動く。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

TIERS = ["ideal", "principle", "rule", "custom"]
TIER_LABEL = {"ideal": "理念", "principle": "原則", "rule": "規則", "custom": "慣習"}
TIER_PREFIX = {"ideal": "I", "principle": "P", "rule": "R", "custom": "C"}
PREFIX_TIER = {v: k for k, v in TIER_PREFIX.items()}
TIER_LOCATION = {
    "ideal": "00-ideals.md",
    "principle": "10-principles/",
    "rule": "20-rules/",
    "custom": "30-customs/",
}

REQUIRED = {
    "ideal": [],
    "principle": ["強度", "根拠", "検査"],
    "rule": ["強度", "根拠", "適用点", "検査", "違反時"],
    "custom": ["強度", "根拠"],
}
OPTIONAL = {
    "ideal": [],
    "principle": [],
    "rule": ["例外"],
    "custom": ["検査"],
}
STRENGTH = {
    "principle": {"MUST", "MUST NOT"},
    "rule": {"MUST", "MUST NOT"},
    "custom": {"SHOULD", "SHOULD NOT", "MAY"},
}
APPLY_POINTS = {"input", "plan", "tool_call", "output"}
ON_VIOLATION = {"block", "refine", "escalate"}
MAX_IDEALS = 7

ARTICLE_HEADING = re.compile(r"^## ([A-Z])-(\d+)\s+(\S.*)$")
FIELD_LINE = re.compile(r"^- ([^:：]+?)\s*[:：]\s*(.*)$")
ID_REF = re.compile(r"^[A-Z]-\d+$")


@dataclass
class Article:
    id: str
    title: str
    tier: str
    path: Path
    line: int
    fields: dict[str, tuple[str, int]] = field(default_factory=dict)
    body_lines: list[str] = field(default_factory=list)
    sections: dict[str, list[str]] = field(default_factory=dict)

    @property
    def body(self) -> str:
        return "\n".join(self.body_lines).strip()

    @property
    def has_body(self) -> bool:
        return bool(self.body)

    def get(self, name: str) -> str:
        return self.fields[name][0] if name in self.fields else ""

    def refs(self) -> list[str]:
        return split_list(self.get("根拠"))


@dataclass
class Finding:
    path: Path
    line: int
    code: str
    message: str

    @property
    def is_error(self) -> bool:
        return self.code.startswith("E")

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.code} {self.message}"


def split_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def parse_check(value: str) -> tuple[str, str]:
    """`検査` の値を (方式, ガードのパス) に分ける。"""
    parts = value.split(None, 1)
    if not parts:
        return "", ""
    return parts[0], parts[1].strip().strip("`") if len(parts) > 1 else ""


def parse_frontmatter(lines: list[str]) -> tuple[dict[str, str], int]:
    """frontmatter の内容と、本文が始まる行の添字を返す。"""
    if not lines or lines[0].strip() != "---":
        return {}, 0
    meta: dict[str, str] = {}
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return meta, i + 1
        if ":" in lines[i]:
            key, value = lines[i].split(":", 1)
            meta[key.strip()] = value.strip()
    return {}, 0


def parse_file(path: Path, tier: str, start: int, lines: list[str], findings: list[Finding]) -> list[Article]:
    articles: list[Article] = []
    current: Article | None = None
    sink: list[str] = []
    in_fields = False
    in_fence = False
    in_comment = False

    for idx in range(start, len(lines)):
        line = lines[idx]
        lineno = idx + 1
        stripped = line.strip()

        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if not in_fence and stripped.startswith("<!--"):
            if "-->" not in line:
                in_comment = True
            continue
        if stripped.startswith("```"):
            in_fence = not in_fence
            in_fields = False
            if current:
                sink.append(line)
            continue
        if in_fence:
            if current:
                sink.append(line)
            continue

        if line.startswith("## "):
            m = ARTICLE_HEADING.match(line)
            if not m:
                findings.append(Finding(path, lineno, "E003", f"見出しが条文 ID 形式ではありません: {stripped}"))
                current = None
                continue
            prefix, number, title = m.groups()
            current = Article(f"{prefix}-{number}", title.strip(), tier, path, lineno)
            articles.append(current)
            sink = current.body_lines
            in_fields = True
            continue

        if current is None:
            continue
        if line.startswith("### "):
            sink = current.sections.setdefault(stripped[4:].strip(), [])
            in_fields = False
            continue
        if in_fields:
            if not stripped:
                continue
            m = FIELD_LINE.match(line)
            if m:
                current.fields[m.group(1).strip()] = (m.group(2).strip(), lineno)
                continue
            in_fields = False
        sink.append(line)

    return articles


def load(root: Path, findings: list[Finding]) -> list[Article]:
    articles: list[Article] = []
    for path in sorted(root.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        meta, start = parse_frontmatter(lines)
        tier = meta.get("tier", "")
        if tier not in TIERS:
            findings.append(
                Finding(path, 1, "E001", f"frontmatter の tier が不正です: '{tier}'（{' / '.join(TIERS)} のいずれか）")
            )
            continue
        rel = path.relative_to(root).as_posix()
        expected = TIER_LOCATION[tier]
        if not (rel == expected or (expected.endswith("/") and rel.startswith(expected))):
            findings.append(
                Finding(path, 1, "E002", f"tier '{tier}' のファイルは {expected} に置いてください（現在: {rel}）")
            )
        articles.extend(parse_file(path, tier, start, lines, findings))
    return articles


def check_article(a: Article, root: Path, by_id: dict[str, Article], findings: list[Finding]) -> None:
    def add(code: str, message: str, line: int | None = None) -> None:
        findings.append(Finding(a.path, line or a.line, code, f"{a.id}: {message}"))

    label = TIER_LABEL[a.tier]
    if PREFIX_TIER.get(a.id[0]) != a.tier:
        add("E004", f"{label}の ID は {TIER_PREFIX[a.tier]}- で始めてください")

    allowed = REQUIRED[a.tier] + OPTIONAL[a.tier]
    for name in REQUIRED[a.tier]:
        if name not in a.fields:
            add("E006", f"必須フィールド `{name}` がありません")
        elif not a.fields[name][0]:
            add("E008", f"`{name}` が空です", a.fields[name][1])
    for name, (_, line) in a.fields.items():
        if name not in allowed:
            add("E007", f"{label}では `{name}` を使えません", line)

    if "強度" in a.fields and a.tier in STRENGTH:
        value, line = a.fields["強度"]
        if value and value not in STRENGTH[a.tier]:
            options = " / ".join(sorted(STRENGTH[a.tier]))
            add("E008", f"{label}の `強度` は {options} のいずれかです（現在: {value}）", line)

    if "適用点" in a.fields:
        value, line = a.fields["適用点"]
        for point in split_list(value):
            if point not in APPLY_POINTS:
                add("E008", f"`適用点` が不正です: {point}（{' / '.join(sorted(APPLY_POINTS))}）", line)

    if "違反時" in a.fields:
        value, line = a.fields["違反時"]
        if value and value not in ON_VIOLATION:
            add("E008", f"`違反時` が不正です: {value}（{' / '.join(sorted(ON_VIOLATION))}）", line)

    if "検査" in a.fields:
        value, line = a.fields["検査"]
        method, guard = parse_check(value)
        if method == "deterministic":
            if not guard:
                add("E008", "`検査: deterministic` にはガードのパスが必要です", line)
            elif not (root / guard).is_file():
                add("E011", f"ガードのファイルがありません: {guard}", line)
        elif value and value != "judge":
            add("E008", f"`検査` は judge または deterministic <パス> です（現在: {value}）", line)

    if "根拠" in a.fields:
        line = a.fields["根拠"][1]
        for ref in a.refs():
            if not ID_REF.match(ref) or ref not in by_id:
                add("E009", f"根拠 {ref} は定義されていません", line)
                continue
            parent = by_id[ref]
            if TIERS.index(parent.tier) >= TIERS.index(a.tier):
                add(
                    "E010",
                    f"根拠 {ref} は{TIER_LABEL[parent.tier]}です。{label}の根拠は上位層の条文に限ります",
                    line,
                )

    if not a.has_body:
        add("E012", "本文がありません")

    if a.tier == "rule":
        missing = [s for s in ("適合例", "違反例") if s not in a.sections]
        if missing:
            add("W003", "`### " + "` と `### ".join(missing) + "` がありません")


def children_map(articles: list[Article]) -> dict[str, list[Article]]:
    children: dict[str, list[Article]] = {}
    for a in articles:
        for ref in a.refs():
            children.setdefault(ref, []).append(a)
    return children


def has_rule_descendant(start: str, children: dict[str, list[Article]]) -> bool:
    seen = {start}
    stack = [start]
    while stack:
        for child in children.get(stack.pop(), []):
            if child.tier == "rule":
                return True
            if child.id not in seen:
                seen.add(child.id)
                stack.append(child.id)
    return False


def lint(root: Path) -> tuple[list[Article], list[Finding]]:
    """条文と検査結果を返す。条文は ID が重複していても読み込んだ順にすべて含む。"""
    findings: list[Finding] = []
    articles = load(root, findings)
    if not articles:
        findings.append(Finding(root, 1, "E013", "条文が 1 つも見つかりません"))
        return articles, findings

    by_id: dict[str, Article] = {}
    for a in articles:
        if a.id in by_id:
            first = by_id[a.id]
            findings.append(
                Finding(a.path, a.line, "E005", f"{a.id}: ID が重複しています（先の定義: {first.path}:{first.line}）")
            )
        else:
            by_id[a.id] = a

    for a in articles:
        check_article(a, root, by_id, findings)

    children = children_map(articles)
    ideals = [a for a in by_id.values() if a.tier == "ideal"]
    for a in ideals:
        if not has_rule_descendant(a.id, children):
            findings.append(
                Finding(a.path, a.line, "W001", f"{a.id}: この理念を具体化する規則がありません（執行手段が無い）")
            )
    if len(ideals) > MAX_IDEALS:
        last = ideals[-1]
        findings.append(
            Finding(last.path, last.line, "W002", f"理念が {len(ideals)} 個あります（{MAX_IDEALS} 個以内を推奨）")
        )

    findings.sort(key=lambda f: (str(f.path), f.line, f.code))
    return articles, findings


def format_tree(articles: list[Article]) -> str:
    children = children_map(articles)
    out: list[str] = []

    def walk(a: Article, depth: int, trail: frozenset) -> None:
        out.append(f"{'  ' * depth}{a.id} {a.title}  [{TIER_LABEL[a.tier]}]")
        for child in children.get(a.id, []):
            if child.id not in trail:
                walk(child, depth + 1, trail | {child.id})

    for a in articles:
        if a.tier == "ideal":
            walk(a, 0, frozenset({a.id}))
    return "\n".join(out)
