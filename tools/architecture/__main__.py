"""Entry point: `python -m tools.architecture <command> [options]`.

Consolidated CLI (SP0001 §15 permits consolidation to avoid command
proliferation). Commands: validate | diff | impact | context | duplication |
drift | attest.
"""
from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
