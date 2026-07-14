"""Technology Dependency Graph + common-mode detection (SP0004 D-0004-16/17/18/19,
§11.6/§11.7, INV-0004-11).

Distinct from the Architecture (SP0001), Semantic (SP0002) and Program (SP0003)
graphs (AC-0004-012/013/014). Computes transitive upstream closure to expose
hidden shared dependencies, and classifies apparent provider diversity as
DIVERSITY_REAL / DIVERSITY_PARTIAL / DIVERSITY_COSMETIC: two providers are NOT
independent if they share a critical upstream (cloud, region, identity, gateway,
upstream model, control plane) — multiple providers do not automatically prove
failure-domain diversity (§12.4).
"""
from __future__ import annotations

from collections import deque

from .model import (Finding, P1, P2, COMMON_MODE_DEPENDENCY,
                    COSMETIC_PROVIDER_DIVERSITY, INVALID_TDR)

# upstream domains that constitute a shared FAILURE DOMAIN (D-0004-17/19/60)
CRITICAL_UPSTREAM_KINDS = ("cloud", "region", "identity_dependency",
                           "gateway_dependency", "upstream_model",
                           "upstream_service", "control_plane")


def _edges(graph: dict) -> dict[str, set[str]]:
    """node -> set of direct upstream nodes."""
    up: dict[str, set[str]] = {}
    for n in graph.get("nodes", []):
        up.setdefault(n["node_id"], set())
    for e in graph.get("edges", []):
        up.setdefault(e["from"], set()).add(e["to"])
        up.setdefault(e["to"], set())
    return up


def validate_graph(graph: dict) -> list[Finding]:
    out: list[Finding] = []
    nodes = {n["node_id"] for n in graph.get("nodes", [])}
    for e in graph.get("edges", []):
        if e.get("from") not in nodes:
            out.append(Finding(INVALID_TDR, P1, e.get("from", "-"),
                               "edge 'from' references unknown node", {}))
        if e.get("to") not in nodes:
            out.append(Finding(INVALID_TDR, P1, e.get("to", "-"),
                               "edge 'to' references unknown node", {}))
    return out


def upstream_closure(graph: dict, node_id: str) -> set[str]:
    """Transitive upstream set of node_id (§11.6)."""
    up = _edges(graph)
    out: set[str] = set()
    q = deque(sorted(up.get(node_id, set())))
    while q:
        u = q.popleft()
        if u not in out:
            out.add(u)
            q.extend(sorted(up.get(u, set())))
    return out


def common_upstream(graph: dict, a: str, b: str) -> set[str]:
    """Shared transitive upstream of two nodes (§11.7)."""
    return upstream_closure(graph, a) & upstream_closure(graph, b)


def failure_domain(graph: dict, node_id: str) -> dict:
    """Critical-upstream attributes of a node's failure domain (D-0004-19).
    Missing attributes remain UNKNOWN, never assumed independent."""
    idx = {n["node_id"]: n for n in graph.get("nodes", [])}
    node = idx.get(node_id, {})
    fd = node.get("failure_domain", {})
    return {k: fd.get(k, "UNKNOWN") for k in CRITICAL_UPSTREAM_KINDS}


def classify_diversity(graph: dict, a: str, b: str) -> dict:
    """DIVERSITY_REAL / PARTIAL / COSMETIC for two providers (D-0004-18)."""
    fa, fb = failure_domain(graph, a), failure_domain(graph, b)
    shared = []
    unknown = []
    for k in CRITICAL_UPSTREAM_KINDS:
        va, vb = fa[k], fb[k]
        if va == "UNKNOWN" or vb == "UNKNOWN":
            unknown.append(k)
        elif va == vb:
            shared.append(k)
    common = common_upstream(graph, a, b)
    # sharing even ONE critical failure domain (cloud/region/model/control plane)
    # is a genuine common mode — two "diverse" providers on the same cloud are not
    # independent (red-team F5, INV-0004-11). Reserve PARTIAL for UNKNOWN-only
    # ambiguity with no proven sharing.
    if shared:
        cls = "DIVERSITY_COSMETIC"   # a shared critical failure domain
    elif common:
        cls = "DIVERSITY_PARTIAL"    # shared transitive upstream only (P2 signal)
    elif unknown:
        cls = "DIVERSITY_PARTIAL"    # cannot prove independence -> not REAL
    else:
        cls = "DIVERSITY_REAL"
    return {"provider_a": a, "provider_b": b, "class": cls,
            "shared_failure_domains": sorted(shared),
            "shared_upstream": sorted(common),
            "unknown_dimensions": sorted(unknown)}


def detect_common_mode(graph: dict, provider_groups: list[list[str]]
                       ) -> list[Finding]:
    """For each declared 'independent' provider group, flag shared upstream /
    cosmetic diversity (INV-0004-11). A group claiming resilience via multiple
    providers that actually share a failure domain is a finding."""
    out: list[Finding] = []
    for group in provider_groups:
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                d = classify_diversity(graph, group[i], group[j])
                if d["class"] == "DIVERSITY_COSMETIC":
                    out.append(Finding(
                        COSMETIC_PROVIDER_DIVERSITY, P1,
                        f"{group[i]}|{group[j]}",
                        "providers presented as diverse share "
                        f"{d['shared_failure_domains']} — failure-domain "
                        "diversity is cosmetic", d))
                elif d["shared_upstream"] or d["shared_failure_domains"]:
                    out.append(Finding(
                        COMMON_MODE_DEPENDENCY, P2,
                        f"{group[i]}|{group[j]}",
                        "providers share upstream/failure domain "
                        f"{d['shared_upstream'] or d['shared_failure_domains']}",
                        d))
    return out


def graph_stats(graph: dict) -> dict:
    return {"nodes": len(graph.get("nodes", [])),
            "edges": len(graph.get("edges", []))}
