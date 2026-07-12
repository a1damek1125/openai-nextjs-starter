"""python -m tools.contracts_inventory <command> — the inventory CLI."""
from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
