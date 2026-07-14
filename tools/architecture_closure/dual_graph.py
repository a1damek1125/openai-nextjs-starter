"""Dual-Graph conformance (SP0010 V5 FUNCTION S, §0, D-0010-75..82).

The closure must not trust its own description. Two graphs are built by DISTINCT
constructions and compared:

  * the **Architecture Description Graph (ADG)** — the DECLARED architecture:
    the 10 constitutional interfaces, the 24 AD views, the 13 global invariants,
    the 6 counterfactual controls, and the declared scalar assertions (migration
    frontier v27, the predecessor twin roots). Every ADG node carries an
    Extraction-Firewall source span (extraction.py) — nothing enters as hard
    truth without an on-disk anchor.
  * the **Repository Evidence Graph (REG)** — built INDEPENDENTLY by walking the
    real tree: the governance packages under tools/, the docs/ artifact
    directories, the product access-control symbols, the LIVE migration frontier
    read from finalis/portal/db.py, and the LIVE twin roots read from the
    committed JSON artifacts. The REG is constructed WITHOUT consulting the ADG,
    so it can disagree.

Each ADG node is then classified against the REG into exactly one of five
classes (D-0010-77):

  MATCH               declared and the REG confirms it, consistently
  DECLARED_ONLY       declared but the REG finds no supporting evidence
  IMPLEMENTATION_ONLY REG evidence exists that no ADG node declares
  CONFLICT            declared value X, REG reads a DIFFERENT value  (BLOCKING)
  AMBIGUOUS           REG evidence present but cannot deterministically confirm
                      the specific assertion — fail-closed, never rounded to MATCH

A CONFLICT on any node, or a DECLARED_ONLY / AMBIGUOUS on a CRITICAL node, blocks
closure. IMPLEMENTATION_ONLY is disclosed as assurance debt (P2), except for the
SP0010 verifier package itself, which is expected and whitelisted.

Governance/analysis tooling only; never imported by product code; no external
effect; emits no secret values.
"""
from __future__ import annotations

from pathlib import Path

from .canon import hash_obj
from .model import Finding, P0, P1, P2, DUAL_GRAPH_CLASSES
from . import interfaces as iface_mod, describe, invariants as inv_mod, \
    counterfactual, freeze as freeze_mod, extraction

# tools/ packages that are NOT predecessor constitutions and are expected to be
# present without a constitutional interface node (the SP0010 verifier itself
# plus any pre-constitutional utility). IMPLEMENTATION_ONLY on these is expected.
_WHITELISTED_IMPL = frozenset({"architecture_closure"})


# --------------------------------------------------------------------------- #
# Architecture Description Graph (declared)                                    #
# --------------------------------------------------------------------------- #
def _adg_nodes(root: Path) -> list:
    """Declared nodes, each with Extraction-Firewall source spans (path[:symbol])
    and the concrete assertion the REG will be asked to confirm."""
    nodes = []
    ifaces = iface_mod.build_interfaces(root)
    for sp, iface in sorted(ifaces.items()):
        spans = [extraction.source_span(path=e["ref"])
                 for e in iface["evidence_refs"]]
        nodes.append({"node_id": f"IFACE:{sp}", "kind": "interface",
                      "critical": True, "spans": spans,
                      "assert": {"type": "evidence_any",
                                 "paths": [e["ref"]
                                           for e in iface["evidence_refs"]]}})
    desc = describe.build_description(root)
    for v in desc["views"]:
        paths = [e["ref"] for e in v["evidence"]]
        spans = [extraction.source_span(path=p) for p in paths]
        # views are description artifacts, not critical assurance nodes
        nodes.append({"node_id": f"VIEW:{v['view_id']}", "kind": "view",
                      "critical": False, "spans": spans,
                      "assert": {"type": "evidence_any", "paths": paths}})
    for inv, spec in sorted(inv_mod.GLOBAL_INVARIANTS.items()):
        spans = [extraction.source_span(path=r.split(":", 1)[0],
                                        symbol=(r.split(":", 1)[1]
                                                if ":" in r else None))
                 for r in spec["control_refs"]]
        nodes.append({"node_id": f"INV:{inv}", "kind": "invariant",
                      "critical": bool(spec["critical"]), "spans": spans,
                      "assert": {"type": "controls_all",
                                 "refs": list(spec["control_refs"])}})
    for ctl, spec in sorted(counterfactual.CONTROLS.items()):
        sym = spec.get("symbol") or None
        spans = [extraction.source_span(path=spec["grounding"], symbol=sym)]
        nodes.append({"node_id": f"CTL:{ctl}", "kind": "control",
                      "critical": bool(spec["critical"]), "spans": spans,
                      "assert": {"type": "control_grounded",
                                 "path": spec["grounding"], "symbol": sym}})
    # declared scalar assertions
    nodes.append({"node_id": "SCALAR:migration_frontier", "kind": "scalar",
                  "critical": True,
                  "spans": [extraction.source_span(
                      path="finalis/portal/db.py", symbol="MIGRATIONS")],
                  "assert": {"type": "frontier_equals",
                             "value": freeze_mod.FRONTIER_VERSION}})
    for name, (rel, key) in sorted(freeze_mod.TWIN_ROOT_SOURCES.items()):
        nodes.append({"node_id": f"SCALAR:twin_root:{name}", "kind": "scalar",
                      "critical": True,
                      "spans": [extraction.source_span(path=rel)],
                      "assert": {"type": "twin_root_present",
                                 "path": rel, "key": key}})
    return nodes


def architecture_description_graph(root: Path) -> dict:
    nodes = _adg_nodes(root)
    fw = extraction.firewall(root, [
        {"node_id": n["node_id"], "critical": n["critical"],
         "spans": n["spans"], "extracted": False} for n in nodes])
    grounding = {g["node_id"]: g for g in fw["nodes"]}
    for n in nodes:
        n["grounding"] = grounding[n["node_id"]]["grounding"]
        n["hard_truth"] = grounding[n["node_id"]]["hard_truth"]
    return {"nodes": nodes, "firewall": fw,
            "adg_root": hash_obj(sorted(n["node_id"] for n in nodes))}


# --------------------------------------------------------------------------- #
# Repository Evidence Graph (independently scanned)                            #
# --------------------------------------------------------------------------- #
def _live_frontier(root: Path) -> int:
    return freeze_mod._migration_frontier(root)


def _live_twin_root(root: Path, rel: str, key: str):
    import json
    p = root / rel
    if not p.exists():
        return None
    try:
        return json.load(open(p, encoding="utf-8")).get(key, "ABSENT")
    except (ValueError, OSError):
        return "UNREADABLE"


def repository_evidence_graph(root: Path) -> dict:
    """Walk the real tree. This construction never consults the ADG."""
    tools_pkgs = {}
    tools_dir = root / "tools"
    if tools_dir.is_dir():
        for child in sorted(tools_dir.iterdir()):
            if child.is_dir() and (child / "__init__.py").exists():
                tools_pkgs[f"tools/{child.name}"] = child.name
    docs_dirs = {}
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        for child in sorted(docs_dir.iterdir()):
            if child.is_dir():
                docs_dirs[f"docs/{child.name}"] = child.name
    # product access-control symbols (independent existence probes)
    app = root / "finalis" / "portal" / "app.py"
    db = root / "finalis" / "portal" / "db.py"
    app_text = app.read_text(encoding="utf-8", errors="replace") if app.exists() else ""
    db_text = db.read_text(encoding="utf-8", errors="replace") if db.exists() else ""
    symbols = {s: (s in app_text or s in db_text)
               for s in ("require_permission", "require_role", "current_user",
                         "tenant_id")}
    twin_roots = {name: _live_twin_root(root, rel, key)
                  for name, (rel, key) in freeze_mod.TWIN_ROOT_SOURCES.items()}
    reg = {
        "tools_packages": tools_pkgs,
        "docs_directories": docs_dirs,
        "access_control_symbols": symbols,
        "live_migration_frontier": _live_frontier(root),
        "live_twin_roots": twin_roots,
    }
    reg["reg_root"] = hash_obj({
        "pkgs": sorted(tools_pkgs), "docs": sorted(docs_dirs),
        "symbols": symbols, "frontier": reg["live_migration_frontier"],
        "twins": twin_roots})
    return reg


# --------------------------------------------------------------------------- #
# Comparison                                                                   #
# --------------------------------------------------------------------------- #
def _exists(root: Path, rel: str) -> bool:
    return (root / rel).exists()


def _classify(root: Path, node: dict, reg: dict) -> tuple:
    """Return (class, detail). Fail-closed: unresolved -> AMBIGUOUS, not MATCH."""
    a = node["assert"]
    t = a["type"]
    if t in ("evidence_any",):
        present = [p for p in a["paths"] if _exists(root, p)]
        if present:
            return "MATCH", {"present": present}
        return "DECLARED_ONLY", {"declared_paths": a["paths"]}
    if t == "controls_all":
        results = {r: inv_mod._control_present(root, r) for r in a["refs"]}
        if all(results.values()):
            return "MATCH", {"controls": results}
        # some declared control ref is absent on disk => the declared invariant
        # is contradicted by the repository (fail-closed CONFLICT for a symbol
        # that was declared present but is missing)
        return "CONFLICT", {"controls": results}
    if t == "control_grounded":
        p = root / a["path"]
        if not p.exists():
            return "DECLARED_ONLY", {"path": a["path"]}
        sym = a.get("symbol")
        if not sym:
            return "MATCH", {"path": a["path"]}
        if p.is_dir():
            return "AMBIGUOUS", {"path": a["path"], "symbol": sym,
                                 "reason": "dir_symbol_uncheckable"}
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "AMBIGUOUS", {"path": a["path"], "reason": "unreadable"}
        if sym in text:
            return "MATCH", {"path": a["path"], "symbol": sym}
        return "CONFLICT", {"path": a["path"], "symbol": sym,
                            "reason": "declared_symbol_absent"}
    if t == "frontier_equals":
        live = reg["live_migration_frontier"]
        if live == a["value"]:
            return "MATCH", {"declared": a["value"], "live": live}
        return "CONFLICT", {"declared": a["value"], "live": live}
    if t == "twin_root_present":
        live = reg["live_twin_roots"].get(_twin_name(node["node_id"]))
        if live in (None, "ABSENT"):
            return "DECLARED_ONLY", {"path": a["path"]}
        if live == "UNREADABLE":
            return "AMBIGUOUS", {"path": a["path"], "reason": "unreadable"}
        return "MATCH", {"path": a["path"], "root": str(live)[:12]}
    return "AMBIGUOUS", {"reason": "unknown_assertion"}


def _twin_name(node_id: str) -> str:
    return node_id.split(":", 2)[-1]


def _declared_prefixes(adg: dict) -> set:
    """The tools/ package prefixes any ADG node grounds to (for detecting
    IMPLEMENTATION_ONLY repository packages)."""
    prefixes = set()
    for n in adg["nodes"]:
        for s in n["spans"]:
            p = s["path"]
            if p.startswith("tools/"):
                parts = p.split("/")
                if len(parts) >= 2:
                    prefixes.add(f"tools/{parts[1]}")
    return prefixes


def compare(root: Path, adg: dict, reg: dict) -> dict:
    classified = []
    for n in adg["nodes"]:
        cls, detail = _classify(root, n, reg)
        # firewall override: a node that is not hard truth cannot be MATCH. The
        # default is fail-closed (a node missing its grounding flag is treated as
        # NOT hard truth), so an ungrounded/unlabelled declaration is never
        # silently promoted to MATCH (D-0010-77).
        if cls == "MATCH" and not n.get("hard_truth", False):
            cls = "AMBIGUOUS"
            detail = {**detail, "reason": "ungrounded_declaration"}
        assert cls in DUAL_GRAPH_CLASSES
        classified.append({"node_id": n["node_id"], "kind": n["kind"],
                           "critical": n["critical"], "class": cls,
                           "detail": detail})
    # IMPLEMENTATION_ONLY: REG governance packages no ADG node declares
    declared = _declared_prefixes(adg)
    impl_only = []
    for pkg_path, name in sorted(reg["tools_packages"].items()):
        if pkg_path not in declared and name not in _WHITELISTED_IMPL:
            impl_only.append(pkg_path)
            classified.append({"node_id": f"REG-PKG:{pkg_path}", "kind": "package",
                               "critical": False, "class": "IMPLEMENTATION_ONLY",
                               "detail": {"package": pkg_path}})
    counts = {c: sum(1 for x in classified if x["class"] == c)
              for c in DUAL_GRAPH_CLASSES}
    return {
        "nodes": classified,
        "class_counts": counts,
        "implementation_only_packages": impl_only,
        "adg_root": adg["adg_root"],
        "reg_root": reg["reg_root"],
        "conformant": counts["CONFLICT"] == 0 and all(
            x["class"] in ("MATCH", "IMPLEMENTATION_ONLY")
            or not x["critical"] for x in classified),
        "dual_graph_root": hash_obj(sorted(
            (x["node_id"], x["class"]) for x in classified)),
    }


def build_dual_graph(root: Path) -> dict:
    adg = architecture_description_graph(root)
    reg = repository_evidence_graph(root)
    cmp = compare(root, adg, reg)
    return {"architecture_description_graph": adg,
            "repository_evidence_graph": reg,
            "comparison": cmp}


def dual_graph_findings(dg: dict) -> list[Finding]:
    out: list[Finding] = []
    for x in dg["comparison"]["nodes"]:
        cls = x["class"]
        crit = x["critical"]
        if cls == "CONFLICT":
            out.append(Finding(
                "DUAL_GRAPH_CONFLICT", P0, x["node_id"],
                "declared architecture conflicts with repository evidence: the "
                "description asserts what the tree contradicts (D-0010-77)",
                x["detail"]))
        elif cls == "DECLARED_ONLY" and crit:
            out.append(Finding(
                "DUAL_GRAPH_DECLARED_ONLY", P0, x["node_id"],
                "critical declared node has no supporting repository evidence "
                "(declared-only): fail-closed (D-0010-78)", x["detail"]))
        elif cls == "DECLARED_ONLY":
            out.append(Finding(
                "DUAL_GRAPH_DECLARED_ONLY", P2, x["node_id"],
                "declared (description-only) node with no repository evidence — "
                "recorded, not counted as implemented", x["detail"]))
        elif cls == "AMBIGUOUS" and crit:
            out.append(Finding(
                "DUAL_GRAPH_AMBIGUOUS", P1, x["node_id"],
                "critical node's repository evidence is ambiguous: cannot be "
                "deterministically confirmed, so not admitted as MATCH "
                "(fail-closed, D-0010-79)", x["detail"]))
        elif cls == "AMBIGUOUS":
            out.append(Finding(
                "DUAL_GRAPH_AMBIGUOUS", P2, x["node_id"],
                "node's repository evidence is ambiguous (disclosed)",
                x["detail"]))
        elif cls == "IMPLEMENTATION_ONLY":
            out.append(Finding(
                "DUAL_GRAPH_IMPLEMENTATION_ONLY", P2, x["node_id"],
                "repository evidence present that the architecture description "
                "does not declare (assurance debt, not a conflict)", x["detail"]))
    return out


def dual_graph_root(dg: dict) -> str:
    return dg["comparison"]["dual_graph_root"]
