"""Semantic Constitution CLI (SP0002 §15).

    python -m tools.semantics validate
    python -m tools.semantics resolve --term completed [--lang en]
    python -m tools.semantics impact --concept lifecycle.completion
    python -m tools.semantics context --concept work.owned_work[,work.task]
    python -m tools.semantics attest
    python -m tools.semantics drift

All deterministic, --json, no network. Exit 1 iff semantically invalid (P0/P1).
This tooling never imports product code.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from .capsule import generate as gen_capsule
from .canon import core_hash
from .drift import snapshot_vector
from .epochs import registry_hash
from .impact import impact_cone
from .lggt_bridge import detect_collisions, validate_mapping
from .multilingual import validate_labels
from .projections import validate_projections
from .registry import load_registry, validate_registry
from .resolve import Resolver

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOCS = os.path.join(REPO_ROOT, "docs", "semantics")
REGISTRY = os.path.join(DOCS, "FINALIS_CANONICAL_CONCEPT_REGISTRY.json")
LGGT = os.path.join(DOCS, "FINALIS_LGGT_SEMANTIC_BRIDGE.json")


def _emit(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))


def _full_validate() -> tuple[dict, dict]:
    reg = load_registry(REGISTRY)
    rep = validate_registry(reg)
    for f in validate_labels(reg):
        rep.add(f)
    for f in validate_projections(reg):
        rep.add(f)
    if os.path.exists(LGGT):
        mappings = json.load(open(LGGT, encoding="utf-8")).get("mappings", [])
        for m in mappings:
            for f in validate_mapping(m):
                rep.add(f)
        for f in detect_collisions(mappings):
            rep.add(f)
    return reg, rep.to_dict()


def cmd_validate(a):
    _reg, d = _full_validate()
    _emit(d)
    return 0 if d["valid"] else 1


def cmd_resolve(a):
    reg = load_registry(REGISTRY)
    out = Resolver(reg).resolve(a.term, lang=a.lang)
    _emit(out)
    return 0 if out["status"] == "RESOLVED" else 1


def cmd_impact(a):
    reg = load_registry(REGISTRY)
    _emit(impact_cone(reg, a.concept.split(",")))
    return 0


def cmd_context(a):
    reg = load_registry(REGISTRY)
    out = gen_capsule(reg, a.concept.split(","), epoch_id=reg.get("active_epoch"),
                      level=a.level, lang=a.lang)
    _emit(out)
    return 0


def cmd_drift(a):
    reg, conf = _full_validate()
    _emit(snapshot_vector(reg, conf, epoch_id=reg.get("active_epoch")))
    return 0


def cmd_attest(a):
    reg, conf = _full_validate()
    core = {"registry_hash": registry_hash(reg),
            "active_epoch": reg.get("active_epoch"),
            "p0_findings": conf["counts"]["P0"],
            "p1_findings": conf["counts"]["P1"]}
    env = dict(core)
    env["semantic_valid"] = conf["valid"]
    env["classification"] = "EVIDENCE_NOT_AUTHORITY"
    env["envelope_hash"] = core_hash(core)
    _emit(env)
    return 0 if conf["valid"] else 1


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    p = argparse.ArgumentParser(prog="tools.semantics", parents=[common],
                                description="Finalis Semantic Operating Constitution")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", parents=[common]).set_defaults(func=cmd_validate)
    r = sub.add_parser("resolve", parents=[common])
    r.add_argument("--term", required=True); r.add_argument("--lang", default=None)
    r.set_defaults(func=cmd_resolve)
    im = sub.add_parser("impact", parents=[common])
    im.add_argument("--concept", required=True); im.set_defaults(func=cmd_impact)
    c = sub.add_parser("context", parents=[common])
    c.add_argument("--concept", required=True); c.add_argument("--level", type=int, default=3)
    c.add_argument("--lang", default="en"); c.set_defaults(func=cmd_context)
    sub.add_parser("drift", parents=[common]).set_defaults(func=cmd_drift)
    sub.add_parser("attest", parents=[common]).set_defaults(func=cmd_attest)
    return p


def main(argv):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
