"""倫理階層（理念 > 原則 > 規則 > 慣習）の検査とコンパイル。

DSPy との接続は `ethic_layer.dspy_adapter` にあり、DSPy を入れた環境でだけ読み込む。
"""

from .compiler import Compiled, CompiledArticle, EthicsCompileError, Violation, compile_ethics
from .spec import Article, Finding, lint

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
