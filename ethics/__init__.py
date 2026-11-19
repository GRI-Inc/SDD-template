"""倫理階層（理念 > 原則 > 規則 > 慣習）。

このディレクトリは、条文（Markdown）と、条文を適用するための道具（`.tools/`）を
まとめて持つ。ディレクトリごと別のリポジトリへ持ち出せる。

    python3 -m ethics lint ethics --strict --tree
    python3 -m ethics sync

道具は `.tools/` に置き、条文のファイルと混ざらないようにしている。名前がドットで
始まるディレクトリは通常の import では辿れないので、このパッケージの探索先に加え、
`ethics.spec`、`ethics.compiler`、`ethics.dspy_adapter` などとして読めるようにする。
"""

from pathlib import Path

__path__.append(str(Path(__file__).resolve().parent / ".tools"))

from .compiler import Compiled, CompiledArticle, EthicsCompileError, Violation, compile_ethics  # noqa: E402
from .spec import Article, Finding, lint  # noqa: E402

__all__ = [
    "Article",
    "Compiled",
    "CompiledArticle",
    "EthicsCompileError",
    "Finding",
    "Violation",
    "compile_ethics",
    "lint",
]
