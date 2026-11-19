"""`python3 -m ethics <command>` の入口。本体は `.tools/cli.py`。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
