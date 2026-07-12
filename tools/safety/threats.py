"""Threat Registry (SP0005 §10, D-0005-04, INV-0005-02).

A THREAT is an adversarial/failure source (prompt injection, tool misuse, memory
poisoning, …) — kept STRICTLY distinct from hazard/loss/risk (INV-0005-02).
External taxonomies (OWASP ASI, MITRE ATLAS, NIST) are mapped as threat INPUTS,
never adopted as the Finalis hazard model (D-0005-81, §5.13).
"""
from __future__ import annotations

from .model import Finding, P1, INVALID_SAFETY_SCHEMA

EXTERNAL_TAXONOMIES = {"OWASP_ASI_2026", "OWASP_AGENTIC_THREATS", "MITRE_ATLAS",
                       "NIST_AI_RMF", "NIST_600_1", "INTERNAL"}


def validate_threats(reg: dict) -> list[Finding]:
    out: list[Finding] = []
    seen: set[str] = set()
    hazards = {h["hazard_id"] for h in reg.get("hazards", [])} \
        if "hazards" in reg else None
    for t in reg.get("threats", []):
        tid = t.get("threat_id")
        if not tid:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, "-",
                               "threat missing threat_id", {}))
            continue
        if tid in seen:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, tid,
                               "duplicate threat_id", {}))
        seen.add(tid)
        src = t.get("external_taxonomy")
        if src is not None and src not in EXTERNAL_TAXONOMIES:
            out.append(Finding(INVALID_SAFETY_SCHEMA, P1, tid,
                               f"unknown external_taxonomy {src!r}", {}))
    return out
