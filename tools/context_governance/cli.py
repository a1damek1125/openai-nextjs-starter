"""Read-only CLI for the Context Governance kernel (TOOL-B10 §20).

Subcommands emit canonical JSON to stdout and open no external effect:
  validate   run the invariant self-check
  invariants list the invariants the kernel enforces
  info       print kernel identity / classification

  python -m tools.context_governance validate
"""
from __future__ import annotations

import sys

from .canon import canonical_json
from . import (CLASSIFICATION, KERNEL_ID, KERNEL_VERSION, validate as val_mod,
               boundary)


def _emit(obj) -> None:
    sys.stdout.write(canonical_json(obj) + "\n")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "info"

    # the CLI itself performs only pure computation
    if not boundary.assert_pure(["PURE_COMPUTE"]):     # pragma: no cover
        _emit({"error": "boundary violation"})
        return 2

    if cmd == "validate":
        res = val_mod.validate()
        _emit(res)
        return 0 if res["ok"] else 1
    if cmd == "invariants":
        _emit({"invariants": list(val_mod.INVARIANTS)})
        return 0
    if cmd == "info":
        _emit({"kernel_id": KERNEL_ID, "version": KERNEL_VERSION,
               "classification": CLASSIFICATION,
               "informs_not_authorizes": True, "live_external_effect": False})
        return 0
    _emit({"error": f"unknown command {cmd!r}",
           "commands": ["validate", "invariants", "info"]})
    return 2


if __name__ == "__main__":            # pragma: no cover
    raise SystemExit(main())
