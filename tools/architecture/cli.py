"""Architecture Immune System CLI (SP0001 §15).

    python -m tools.architecture.validate            # full conformance gate
    python -m tools.architecture.diff --base <commit> # diff-aware delta
    python -m tools.architecture.impact --capability <id>
    python -m tools.architecture.context --capability <id>
    python -m tools.architecture.attest --base <commit>  # proof envelope

All commands support --json. No network required. Exit code 1 iff the
architecture is INVALID (P0>0 or P1>0). This tooling never imports product code.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from .conformance import evaluate
from .context_spine import generate as gen_spine
from .diff import architecture_delta
from .drift import snapshot_vector
from .duplication import candidates as dup_candidates
from .envelope import build_envelope
from .impact import impact_cone
from .intent import classify_delta, validate_intent
from .manifest import load_twin, validate_twin
from .observe import build_observed
from .waivers import (active_scopes, expired_findings, invalid_waiver_findings,
                      status_report)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TWIN_PATH = os.path.join(REPO_ROOT, "docs", "architecture",
                         "FINALIS_1000_ARCHITECTURE_TWIN.json")
WAIVERS_PATH = os.path.join(REPO_ROOT, "docs", "architecture",
                            "FINALIS_1000_ARCHITECTURE_WAIVERS.json")


def _load_waivers() -> list[dict]:
    if os.path.exists(WAIVERS_PATH):
        data = json.load(open(WAIVERS_PATH, encoding="utf-8"))
        return data.get("waivers", [])
    return []


def _emit(obj: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))


def _run_conformance(now: str) -> tuple[dict, Any, Any]:
    twin = load_twin(TWIN_PATH)
    terr = validate_twin(twin)
    observed = build_observed(REPO_ROOT)
    waivers = _load_waivers()
    max_days = twin.get("waiver_policy", {}).get("max_lifetime_days", 90)
    scopes = active_scopes(waivers, now, max_days)   # VALID waivers only
    rep = evaluate(twin, observed, active_waivers=scopes)
    for f in expired_findings(waivers, now):
        rep.add(f)
    for f in invalid_waiver_findings(waivers, now, max_days):  # tampering visible
        rep.add(f)
    d = rep.to_dict()
    d["twin_validation_errors"] = terr
    d["waivers"] = status_report(waivers, now)
    if terr:
        d["valid"] = False
    return twin, observed, d


def cmd_validate(args: argparse.Namespace) -> int:
    _twin, _obs, d = _run_conformance(args.now)
    _emit(d, args.json)
    return 0 if d["valid"] else 1


def cmd_diff(args: argparse.Namespace) -> int:
    twin, observed, conf = _run_conformance(args.now)
    delta = architecture_delta(twin, observed)
    intent = None
    if args.intent and os.path.exists(args.intent):
        intent = json.load(open(args.intent, encoding="utf-8"))
    classification = classify_delta(intent, delta)
    out = {"base_commit": args.base or twin.get("baseline_head"),
           "delta": delta, "intent_classification": classification,
           "conformance_valid": conf["valid"]}
    _emit(out, args.json)
    hard = not conf["valid"]
    return 1 if (hard or not classification["is_clean"]) else 0


def cmd_impact(args: argparse.Namespace) -> int:
    twin = load_twin(TWIN_PATH)
    observed = build_observed(REPO_ROOT)
    out = impact_cone(twin, observed, args.capability.split(","),
                      max_depth=args.max_depth)
    _emit(out, args.json)
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    twin = load_twin(TWIN_PATH)
    try:
        out = gen_spine(twin, args.capability)
    except KeyError as e:
        _emit({"error": str(e)}, args.json)
        return 1
    _emit(out, args.json)
    return 0


def cmd_duplication(args: argparse.Namespace) -> int:
    twin = load_twin(TWIN_PATH)
    out = dup_candidates(twin, threshold=args.threshold)
    _emit({"threshold": args.threshold, "candidates": out,
           "note": "DUPLICATION_CANDIDATE is advisory; never proof (INV-0001-07)."},
          args.json)
    return 0


def cmd_drift(args: argparse.Namespace) -> int:
    _twin, observed, conf = _run_conformance(args.now)
    vec = snapshot_vector(conf, observed.to_dict(),
                          active_waivers=conf["waivers"]["active"])
    _emit(vec, args.json)
    return 0


def cmd_attest(args: argparse.Namespace) -> int:
    twin, observed, conf = _run_conformance(args.now)
    delta = architecture_delta(twin, observed)
    intent = None
    if args.intent and os.path.exists(args.intent):
        intent = json.load(open(args.intent, encoding="utf-8"))
        ierr = validate_intent(intent)
        if ierr:
            _emit({"intent_errors": ierr}, args.json)
            return 1
    env = build_envelope(
        base_commit=args.base or twin.get("baseline_head"),
        source_commit=observed.commit, declared_twin=twin,
        observed=observed.to_dict(), architecture_delta=delta,
        conformance=conf, change_intent=intent,
        waiver_set=sorted(active_scopes(_load_waivers(), args.now)),
        test_evidence=args.test_evidence.split(",") if args.test_evidence else [])
    _emit(env, args.json)
    return 0 if env["architecture_valid"] else 1


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--now", default="2026-07-11",
                        help="deterministic 'today' (YYYY-MM-DD) for waiver expiry")
    common.add_argument("--json", action="store_true", help="JSON output")

    p = argparse.ArgumentParser(prog="tools.architecture", parents=[common],
                                description="Finalis Architecture Immune System")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", parents=[common]).set_defaults(func=cmd_validate)

    d = sub.add_parser("diff", parents=[common])
    d.add_argument("--base", default=None)
    d.add_argument("--intent", default=None)
    d.set_defaults(func=cmd_diff)

    im = sub.add_parser("impact", parents=[common])
    im.add_argument("--capability", required=True)
    im.add_argument("--max-depth", type=int, default=None)
    im.set_defaults(func=cmd_impact)

    c = sub.add_parser("context", parents=[common])
    c.add_argument("--capability", required=True)
    c.set_defaults(func=cmd_context)

    du = sub.add_parser("duplication", parents=[common])
    du.add_argument("--threshold", type=float, default=0.55)
    du.set_defaults(func=cmd_duplication)

    sub.add_parser("drift", parents=[common]).set_defaults(func=cmd_drift)

    a = sub.add_parser("attest", parents=[common])
    a.add_argument("--base", default=None)
    a.add_argument("--intent", default=None)
    a.add_argument("--test-evidence", default=None)
    a.set_defaults(func=cmd_attest)
    return p


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
