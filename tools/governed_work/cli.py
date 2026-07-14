"""Repository-local CLI for the Governed Work Constitution (SP0006 §15). Every
subcommand emits JSON (evidence, not authority). No product runtime endpoint.
"""
from __future__ import annotations

import argparse
import json
import sys

from .loader import load_program
from .validate import validate_all
from .modelcheck import run_all_models
from .envelope import work_proof_envelope


def _emit(obj) -> int:
    print(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def cmd_inventory(a) -> int:
    p = load_program()
    return _emit({k: len(v) for k, v in p.items()
                  if isinstance(v, list)})


def cmd_validate(a) -> int:
    rep = validate_all(load_program())
    _emit(rep.to_dict())
    return 0 if rep.valid else 1


def cmd_modelcheck(a) -> int:
    res = run_all_models()
    out = {k: {kk: vv for kk, vv in v.items() if kk != "counterexample"}
           for k, v in res.items()}
    _emit(out)
    return 0 if all(v.get("verdict") == "HOLDS" for v in res.values()) else 1


def cmd_attest(a) -> int:
    p = load_program()
    rep = validate_all(p)
    wo = (p.get("work_orders") or [{}])[0]
    env = work_proof_envelope(
        wo, leases=p.get("leases"),
        delegation_graph=p.get("delegation_edges"),
        approvals=p.get("approval_tokens"),
        outcome_contract=(p.get("outcome_contracts") or [None])[0],
        accountability_chain=(p.get("accountability_chains") or [None])[0])
    _emit({"valid": rep.valid, "counts": rep.counts(),
           "work_proof_envelope": env})
    return 0 if rep.valid else 1


def cmd_compile(a) -> int:
    from .workorder import compile_work_order, validate_work_order
    ci = _load_json(a.candidate)
    bindings = _load_json(a.bindings) if a.bindings else {}
    w = compile_work_order(ci, bindings=bindings)
    return _emit({"work_order": w,
                  "findings": [f.to_dict() for f in validate_work_order(w)]})


def cmd_admit(a) -> int:
    from .admission import admit
    w = _load_json(a.work_order)
    r = admit(w)
    _emit(r)
    return 0 if r["decision"] == "ADMITTED" else 1


def cmd_impact(a) -> int:
    # advisory impact cone over the loaded program for a changed work order
    p = load_program()
    target = a.work_order
    affected = {"leases": [], "delegation_edges": [], "approval_tokens": [],
                "outcome_contracts": [], "recurring_contracts": []}
    for l in p.get("leases", []):
        if l.get("work_order_id") == target:
            affected["leases"].append(l.get("lease_id"))
    for e in p.get("delegation_edges", []):
        if e.get("work_order_id") == target:
            affected["delegation_edges"].append(e.get("delegation_id"))
    for t in p.get("approval_tokens", []):
        affected["approval_tokens"].append(t.get("approval_token_id"))
    for oc in p.get("outcome_contracts", []):
        if oc.get("work_order_id") == target:
            affected["outcome_contracts"].append(oc.get("outcome_contract_id"))
    return _emit({"work_order_id": target, "affected": affected,
                  "classification": "ADVISORY"})


def cmd_roadmap_identity(a) -> int:
    return _emit({
        "sp_id": "SP0006",
        "canonical_title": "Governed Work, Delegated Autonomy & Outcome "
                           "Accountability Constitution",
        "reassignment": "SP0006 reassigned from 'Evaluation and 1000/1000 Score "
                        "Charter' (now SP0011) — authorized non-silent roadmap "
                        "reassignment",
        "report": "docs/governed_work/SP0006_ROADMAP_IDENTITY_REPORT.md",
        "predecessors": ["SP0000", "SP0001", "SP0002", "SP0003", "SP0004",
                         "SP0005"],
        "change_boundary": {"product_behavior_change": False,
                            "external_effects": False, "db_migration": False,
                            "migration_frontier": 27}})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tools.governed_work")
    sub = p.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON output (default)")

    sub.add_parser("roadmap-identity", parents=[common]).set_defaults(
        func=cmd_roadmap_identity)
    sub.add_parser("inventory", parents=[common]).set_defaults(func=cmd_inventory)
    sub.add_parser("validate", parents=[common]).set_defaults(func=cmd_validate)
    sub.add_parser("modelcheck", parents=[common]).set_defaults(func=cmd_modelcheck)
    sub.add_parser("attest", parents=[common]).set_defaults(func=cmd_attest)

    c = sub.add_parser("compile", parents=[common])
    c.add_argument("--candidate", required=True)
    c.add_argument("--bindings")
    c.set_defaults(func=cmd_compile)

    d = sub.add_parser("admit", parents=[common])
    d.add_argument("--work-order", dest="work_order", required=True)
    d.set_defaults(func=cmd_admit)

    im = sub.add_parser("impact", parents=[common])
    im.add_argument("--work-order", dest="work_order", required=True)
    im.set_defaults(func=cmd_impact)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)
