"""Waiver and approval governance (SP0009 D-0009-14, AC-0009-073..080,
INV-0009-42..46).

A waiver is a scoped, expiring, candidate-bound risk acceptance — never a
deletion of the requirement. It requires an expiry, a risk owner and a
compensating control; it binds to ONE candidate genome; it can never apply to a
non-waivable gate or obligation. Approvals are likewise candidate-bound and a
protected candidate can never be approved by the same identity that authored it
(no self-approval, strict identity comparison — never string-truthiness).
"""
from __future__ import annotations

from .canon import hash_obj
from .model import Finding, P0, P1
from .gates import NON_WAIVABLE


def waiver(*, gate_id: str, candidate_genome: str, risk_owner: str,
           compensating_control: str, expires_at: str,
           approved_by: str) -> dict:
    w = {
        "gate_id": gate_id,
        "candidate_genome": candidate_genome,
        "risk_owner": risk_owner,
        "compensating_control": compensating_control,
        "expires_at": expires_at,
        "approved_by": approved_by,
        "status": "PROPOSED",
    }
    w["waiver_id"] = "WV-" + hash_obj(w)[:20]
    return w


def validate_waiver(w: dict, *, candidate_genome: str, now: str,
                    author: str | None = None) -> list[Finding]:
    out: list[Finding] = []
    subject = str(w.get("waiver_id") or "-")
    gid = w.get("gate_id")
    if gid in NON_WAIVABLE:
        out.append(Finding(
            "NON_WAIVABLE_WAIVER_REJECTED", P0, subject,
            f"gate {gid} is on the Non-Waivable Gate Registry; a waiver can "
            "never apply (AC-0009-079)", {"gate_id": gid}))
    if w.get("candidate_genome") != candidate_genome:
        out.append(Finding(
            "WAIVER_INVALID", P0, subject,
            "waiver is bound to a different candidate genome; waivers never "
            "move between candidates (AC-0009-074)", {}))
    if not w.get("expires_at"):
        out.append(Finding("WAIVER_INVALID", P1, subject,
                           "waiver has no expiry (AC-0009-075)", {}))
    elif str(w["expires_at"]) <= str(now):
        out.append(Finding("WAIVER_EXPIRED", P1, subject,
                           "waiver expired (AC-0009-078)",
                           {"expires_at": w["expires_at"], "now": now}))
    if not w.get("risk_owner"):
        out.append(Finding("WAIVER_INVALID", P1, subject,
                           "waiver has no risk owner (AC-0009-076)", {}))
    if not w.get("compensating_control"):
        out.append(Finding("WAIVER_INVALID", P1, subject,
                           "waiver has no compensating control (AC-0009-077)",
                           {}))
    if author is not None and w.get("approved_by") == author:
        out.append(Finding(
            "SELF_APPROVAL_REJECTED", P0, subject,
            "waiver approver is the change author; protected candidates "
            "cannot self-approve (D-0009-14, AC-0009-080)",
            {"author": author}))
    return out


def activate(w: dict, *, candidate_genome: str, now: str,
             author: str | None = None) -> dict:
    fs = validate_waiver(w, candidate_genome=candidate_genome, now=now,
                         author=author)
    if any(f.severity in ("P0", "P1") for f in fs):
        raise ValueError([f.as_dict() for f in fs])
    after = dict(w)
    after["status"] = "ACTIVE"
    return after


# --- approvals (candidate-bound, no self-approval) --------------------------------
def approval(*, candidate_genome: str, approver: str, scope: str,
             expires_at: str | None = None) -> dict:
    a = {"candidate_genome": candidate_genome, "approver": approver,
         "scope": scope, "expires_at": expires_at, "status": "ACTIVE"}
    a["approval_id"] = "AP-" + hash_obj(a)[:20]
    return a


def validate_approval(a: dict, *, candidate_genome: str, author: str,
                      now: str) -> list[Finding]:
    out: list[Finding] = []
    subject = str(a.get("approval_id") or "-")
    if a.get("candidate_genome") != candidate_genome:
        out.append(Finding(
            "WAIVER_INVALID", P0, subject,
            "approval bound to a different candidate; approvals never move "
            "between candidates (INV-0009-45)", {}))
    # strict identity equality — not truthiness, not substring
    if a.get("approver") == author:
        out.append(Finding(
            "SELF_APPROVAL_REJECTED", P0, subject,
            "approver identity equals author identity: self-approval is "
            "rejected for protected candidates (INV-0009-46)",
            {"approver": a.get("approver")}))
    exp = a.get("expires_at")
    if exp is not None and str(exp) <= str(now):
        out.append(Finding("WAIVER_EXPIRED", P1, subject,
                           "approval expired", {"expires_at": exp}))
    return out
