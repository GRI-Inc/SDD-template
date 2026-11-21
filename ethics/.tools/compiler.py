"""倫理階層の条文を、実行時に使う成果物へコンパイルする。

成果物は 3 つ:
  1. 条文集プロンプト   `Compiled.prompt()` / `Compiled.customs_prompt()`
  2. ガード登録表       `Compiled.guards(point)` / `Compiled.check_guards(point, event)`
  3. 判定対象の条文一覧 `Compiled.judged(point)`（metric ゲートが LLM 判定器に渡す）

lint でエラーが出る条文集はコンパイルしない。支配構造が壊れた規範を実行時に持ち込まないため。
標準ライブラリだけで動く。DSPy との接続は `ethics.dspy_adapter` が担う。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from .spec import TIER_LABEL, TIERS, Article, Finding, lint_articles, parse_check, split_list

FROZEN_TIERS = ("ideal", "principle", "rule")
DEFAULT_POINT = "output"

PREAMBLE = """\
# 行動規範

以下は、あなたが従う規範です。
効力は 理念 > 原則 > 規則 の順に強く、衝突したときは上位が優先します。
規則が定めていない場面では原則に、原則も定めていない場面では理念に立ち返って判断してください。
理念・原則・規則からの逸脱は認められません。ただし、規則に「例外」が書かれている場合は、その条件に限って逸脱できます。"""

CUSTOMS_PREAMBLE = "次の慣習を既定の振る舞いとします。理由があれば逸脱してかまいません。"

GuardFn = Callable[[dict], list]


class EthicsCompileError(Exception):
    def __init__(self, message: str, findings: list[Finding] | None = None):
        self.findings = findings or []
        detail = "\n".join(f"  {f}" for f in self.findings)
        super().__init__(f"{message}\n{detail}" if detail else message)


@dataclass(frozen=True)
class CompiledArticle:
    id: str
    title: str
    tier: str
    body: str
    strength: str = ""
    basis: tuple = ()
    points: tuple = ()
    check: str = ""
    guard_path: str = ""
    on_violation: str = ""
    exception: str = ""
    good_examples: tuple = ()
    bad_examples: tuple = ()

    @property
    def label(self) -> str:
        return TIER_LABEL[self.tier]

    def applies_at(self, point: str) -> bool:
        """適用点を持たない条文（原則・慣習）は output で検査する。"""
        return point in self.points if self.points else point == DEFAULT_POINT


@dataclass(frozen=True)
class Violation:
    article_id: str
    title: str
    tier: str
    point: str
    reason: str
    on_violation: str
    lineage: str
    source: str

    @property
    def hard(self) -> bool:
        """慣習以外の違反は、スコアを 0 にする違反として扱う。"""
        return self.tier != "custom"

    def render(self) -> str:
        return f"[{TIER_LABEL[self.tier]}] {self.article_id} {self.title}: {self.reason}（根拠の系譜: {self.lineage}）"


def _examples(lines: list[str]) -> tuple:
    return tuple(line.strip()[2:].strip() for line in lines if line.strip().startswith("- "))


def _compile_article(a: Article) -> CompiledArticle:
    method, guard = parse_check(a.get("検査"))
    return CompiledArticle(
        id=a.id,
        title=a.title,
        tier=a.tier,
        body=a.body,
        strength=a.get("強度"),
        basis=tuple(a.refs()),
        points=tuple(split_list(a.get("適用点"))),
        check=method,
        guard_path=guard,
        on_violation=a.get("違反時"),
        exception=a.get("例外"),
        good_examples=_examples(a.sections.get("適合例", [])),
        bad_examples=_examples(a.sections.get("違反例", [])),
    )


def _load_guard(root: Path, article: CompiledArticle) -> GuardFn:
    path = root / article.guard_path
    name = "ethics_guard_" + hashlib.sha256(str(path).encode()).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise EthicsCompileError(f"{article.id}: ガードを読み込めません: {article.guard_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, "guard", None)
    if not callable(fn):
        raise EthicsCompileError(
            f"{article.id}: ガード {article.guard_path} に `guard(event: dict) -> list[str]` がありません"
        )
    return fn


@dataclass
class Compiled:
    root: Path
    articles: dict[str, CompiledArticle]
    warnings: list[Finding] = field(default_factory=list)
    _guards: dict[str, GuardFn] = field(default_factory=dict, repr=False)

    # --- 参照 ---

    def by_tier(self, tier: str) -> list[CompiledArticle]:
        return [a for a in self.articles.values() if a.tier == tier]

    def lineage(self, article_id: str) -> list[CompiledArticle]:
        """条文から理念まで、根拠を遡った列を返す。根拠が複数あるときは先頭を辿る。"""
        chain = [self.articles[article_id]]
        while chain[-1].basis:
            chain.append(self.articles[chain[-1].basis[0]])
        return chain

    def lineage_text(self, article_id: str) -> str:
        return " ← ".join(f"{a.id} {a.title}" for a in self.lineage(article_id))

    @property
    def digest(self) -> str:
        """条文集の内容のハッシュ。どの版の規範が効いていたかを記録に残すために使う。"""
        payload = json.dumps(self.to_dict()["articles"], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @property
    def unsupported(self) -> list[CompiledArticle]:
        """適用点 plan だけを持つ判定器条文。計画の表現が決まっていないため検査できない。"""
        return [a for a in self.articles.values() if a.check == "judge" and a.points and set(a.points) == {"plan"}]

    # --- 成果物 1: 条文集プロンプト ---

    def _line(self, a: CompiledArticle) -> str:
        head = f"- {a.id}"
        if a.strength:
            head += f" [{a.strength}]"
        head += f" {a.title}"
        if a.basis:
            head += f"（根拠: {', '.join(a.basis)}）"
        body = " ".join(part.strip() for part in a.body.splitlines() if part.strip())
        text = f"{head}: {body}"
        if a.exception:
            text += f" 例外: {a.exception}"
        return text

    def prompt(self, tiers: tuple = FROZEN_TIERS) -> str:
        """凍結して渡す条文集。プロンプト最適化の対象にしない入力として使う。"""
        parts = [PREAMBLE]
        for tier in TIERS:
            if tier not in tiers:
                continue
            items = self.by_tier(tier)
            if items:
                parts.append(f"## {TIER_LABEL[tier]}\n" + "\n".join(self._line(a) for a in items))
        return "\n\n".join(parts)

    def customs_prompt(self) -> str:
        """慣習の条文集。最適化してよい指示文の初期値として使う。慣習が無ければ空文字。"""
        items = self.by_tier("custom")
        if not items:
            return ""
        return CUSTOMS_PREAMBLE + "\n" + "\n".join(self._line(a) for a in items)

    def agent_prompt(self) -> str:
        """4 層すべてを 1 つにまとめた条文集。プロンプトを最適化しないエージェントに、そのまま渡す。"""
        text = self.prompt()
        items = self.by_tier("custom")
        if items:
            text += f"\n\n## {TIER_LABEL['custom']}\n{CUSTOMS_PREAMBLE}\n" + "\n".join(self._line(a) for a in items)
        return text

    def article_text(self, article_id: str) -> str:
        """判定器に渡す、1 条文の全文。根拠の系譜と適合例・違反例を含む。"""
        a = self.articles[article_id]
        lines = [f"{a.label} {a.id} {a.title}"]
        if a.strength:
            lines.append(f"強度: {a.strength}")
        lines.append(f"本文: {a.body}")
        if a.exception:
            lines.append(f"例外（この条件に当たる場合は違反ではない）: {a.exception}")
        ancestors = self.lineage(article_id)[1:]
        if ancestors:
            lines.append("根拠となる上位の条文:")
            lines.extend(f"- {p.label} {p.id} {p.title}: {p.body}" for p in ancestors)
        if a.good_examples:
            lines.append("適合例:")
            lines.extend(f"- {e}" for e in a.good_examples)
        if a.bad_examples:
            lines.append("違反例:")
            lines.extend(f"- {e}" for e in a.bad_examples)
        return "\n".join(lines)

    # --- 成果物 2: ガード登録表 ---

    def guards(self, point: str) -> list[tuple]:
        """適用点 `point` で実行する (条文, ガード関数) の一覧。"""
        return [
            (a, self._guards[a.id])
            for a in self.articles.values()
            if a.check == "deterministic" and a.applies_at(point)
        ]

    def check_guards(self, point: str, event: dict) -> list[Violation]:
        """決定的ガードを実行して違反を返す。ガードが例外を出した場合も違反として扱う（安全側）。"""
        violations: list[Violation] = []
        for article, fn in self.guards(point):
            try:
                reasons = [str(r) for r in (fn({**event, "point": point}) or [])]
            except Exception as err:  # noqa: BLE001 - ガードの不具合で素通りさせない
                reasons = [f"ガードの実行に失敗したため、安全側に倒して違反とみなします: {err!r}"]
            violations.extend(self.violation(article.id, point, reason, "guard") for reason in reasons)
        return violations

    def violation(self, article_id: str, point: str, reason: str, source: str) -> Violation:
        a = self.articles[article_id]
        return Violation(
            article_id=a.id,
            title=a.title,
            tier=a.tier,
            point=point,
            reason=reason,
            on_violation=a.on_violation,
            lineage=self.lineage_text(a.id),
            source=source,
        )

    # --- 成果物 3: 判定対象の条文一覧 ---

    def judged(self, point: str, tiers: tuple = ("principle", "rule", "custom")) -> list[CompiledArticle]:
        """適用点 `point` で LLM 判定器にかける条文の一覧。"""
        return [
            a for a in self.articles.values() if a.check == "judge" and a.tier in tiers and a.applies_at(point)
        ]

    # --- 書き出し ---

    def to_dict(self) -> dict[str, Any]:
        return {
            "tiers": TIERS,
            "articles": [asdict(a) for a in self.articles.values()],
        }

    def to_json(self) -> str:
        data = self.to_dict()
        data["digest"] = self.digest
        return json.dumps(data, ensure_ascii=False, indent=2)


def compile_ethics(root: str | Path = "ethics") -> Compiled:
    """ethics/ を検査し、合格した条文集をコンパイルする。エラーがあれば EthicsCompileError。"""
    root = Path(root)
    if not root.is_dir():
        raise EthicsCompileError(f"ディレクトリがありません: {root}")
    articles, findings = lint_articles(root)
    errors = [f for f in findings if f.is_error]
    if errors:
        raise EthicsCompileError("倫理階層の検査に合格していないため、コンパイルできません", errors)

    compiled = Compiled(
        root=root,
        articles={a.id: _compile_article(a) for a in articles},
        warnings=[f for f in findings if not f.is_error],
    )
    for a in compiled.articles.values():
        if a.check == "deterministic":
            compiled._guards[a.id] = _load_guard(root, a)
    return compiled
