"""CI workflow security and agentic injection taint analysis (SP0009 FUNCTION
J, §11.18, D-0009-41..45, AC-0009-191..205).

Workflow files are protected code (D-0009-41). Deterministic checks: least-
privilege token permissions (missing explicit permission NEVER means unlimited
— fail-closed, D-0009-43), full-SHA pinning of protected actions (a mutable tag
is not identity, D-0009-42), privileged-untrusted-checkout detection
(pull_request_target + checkout of PR head), and TAINT tracking from untrusted
sources (PR body/title/comments/branch names/issue text/model output) into
sinks (agent prompts, shell, repository writes, release decisions). Untrusted
content may provide DATA; it can never provide release AUTHORITY (D-0009-45) —
and a model's output is itself untrusted for authority purposes.
"""
from __future__ import annotations

import re

from .canon import hash_obj
from .model import Finding, P0, P1, TAINT_STATUSES

UNTRUSTED_SOURCES = (
    "ISSUE_BODY", "PR_TITLE", "PR_BODY", "PR_COMMENT", "COMMIT_MESSAGE",
    "BRANCH_NAME", "WORKFLOW_DISPATCH_INPUT", "ARTIFACT_METADATA",
    "TOOL_OUTPUT", "MODEL_OUTPUT",
)
SINKS = ("AGENT_PROMPT", "MODEL_CONTEXT", "SHELL", "GENERATED_COMMAND",
         "FILE_WRITE", "TOOL_CALL", "REPOSITORY_WRITE", "RELEASE_DECISION")
# sinks that constitute AUTHORITY: tainted data reaching these is always P0
AUTHORITY_SINKS = frozenset({"RELEASE_DECISION", "REPOSITORY_WRITE"})
PRIVILEGED_SINKS = frozenset({"SHELL", "GENERATED_COMMAND", "TOOL_CALL",
                              "FILE_WRITE"}) | AUTHORITY_SINKS

# Untrusted context is treated as an ALLOWLIST of trusted contexts, not a
# denylist of known-bad fields (red-team #7): ANY interpolation of
# github.event.* or github.head_ref that is not a known-safe scalar is
# attacker-influenced. A few fields (event.number, event.action) are trusted.
_ANY_UNTRUSTED_CONTEXT = re.compile(r"github\.(event\b|head_ref\b)")
_TRUSTED_CONTEXT_FIELDS = re.compile(
    r"github\.event\.(number|action|inputs\.[A-Za-z_]+"
    r"|pull_request\.(number|state|merged|draft))\b")

_FULL_SHA = re.compile(r"@[0-9a-f]{40}$")

# permissions granted 'write' are allowed ONLY for these low-risk scopes;
# any other write scope (contents, id-token, packages, deployments, …) is
# flagged (allowlist, not a count threshold).
_LOW_RISK_WRITE_SCOPES = frozenset({"checks", "statuses", "pull-requests",
                                    "issues"})


def taint_flow(*, source_kind: str, source_ref: str, sink_kind: str,
               sink_ref: str, transform_steps=(), sanitization_claims=(),
               tool_capabilities=()) -> dict:
    f = {"source_kind": source_kind, "source_ref": source_ref,
         "sink_kind": sink_kind, "sink_ref": sink_ref,
         "transform_steps": list(transform_steps),
         "sanitization_claims": list(sanitization_claims),
         "tool_capabilities": list(tool_capabilities),
         "status": "UNRESOLVED"}
    f["flow_id"] = "TF-" + hash_obj(f)[:20]
    return f


def analyze_flow(flow: dict) -> dict:
    """Resolve a taint flow. Tainted data reaching an AUTHORITY sink is BLOCKED
    unconditionally — no sanitization claim can turn external content into
    release authority (D-0009-45). A privileged sink needs a VERIFIED declared
    safe transformation; a mere claim is not verification."""
    sink = flow.get("sink_kind")
    after = dict(flow)
    if sink in AUTHORITY_SINKS:
        after["status"] = "BLOCKED"
        after["reason"] = ("untrusted content can never provide release "
                          "authority (D-0009-45)")
        return after
    if sink in PRIVILEGED_SINKS or sink in ("AGENT_PROMPT", "MODEL_CONTEXT"):
        verified = [s for s in flow.get("sanitization_claims") or []
                    if isinstance(s, dict) and s.get("verified") is True]
        if verified and sink not in PRIVILEGED_SINKS:
            after["status"] = "SAFE_TRANSFORMED"
            after["verified_transformations"] = [s.get("transform")
                                                 for s in verified]
        elif verified and sink in PRIVILEGED_SINKS:
            # even a verified transformation into a privileged sink stays
            # visible for review — resolved but recorded
            after["status"] = "SAFE_TRANSFORMED"
            after["verified_transformations"] = [s.get("transform")
                                                 for s in verified]
        else:
            after["status"] = "UNRESOLVED"
    assert after["status"] in TAINT_STATUSES
    return after


def flow_findings(flow: dict) -> list[Finding]:
    out: list[Finding] = []
    subject = str(flow.get("flow_id") or "-")
    status = flow.get("status")
    sink = flow.get("sink_kind")
    if status == "BLOCKED":
        out.append(Finding(
            "EXTERNAL_CONTENT_AUTHORITY_REJECTED", P0, subject,
            f"untrusted {flow.get('source_kind')} content flows into "
            f"authority sink {sink}: external content never grants release "
            "authority (D-0009-45, AC-0009-201)", {"flow": subject}))
    elif status == "UNRESOLVED" and sink in PRIVILEGED_SINKS:
        out.append(Finding(
            "AGENTIC_WORKFLOW_INJECTION_PATH", P0, subject,
            f"unresolved taint path {flow.get('source_kind')} -> {sink}: "
            "tainted data can become privileged control without a verified "
            "safe transformation (§11.18)", {}))
    elif status == "UNRESOLVED":
        out.append(Finding(
            "CI_TAINT_UNRESOLVED", P1, subject,
            f"taint path {flow.get('source_kind')} -> {sink} unresolved "
            "(prompt/context injection risk)", {}))
    return out


# --- workflow static checks (deterministic; operate on parsed workflow dicts) --------
def workflow_findings(workflow: dict, *, path: str) -> list[Finding]:
    """Deterministic workflow review: permissions least-privilege, action
    pinning, privileged untrusted checkout, untrusted-context interpolation
    into run: blocks."""
    out: list[Finding] = []
    perms = workflow.get("permissions")
    if perms is None:
        out.append(Finding(
            "CI_TOKEN_OVERPRIVILEGED", P1, path,
            "workflow declares no explicit permissions: missing permission "
            "never means unlimited — declare least privilege (D-0009-43)", {}))
    elif perms == "write-all":
        out.append(Finding(
            "CI_TOKEN_OVERPRIVILEGED", P1, path,
            "workflow grants write-all token permissions", {"permissions": perms}))
    elif isinstance(perms, dict):
        # allowlist: ANY write scope outside the low-risk set is flagged, even
        # a single `contents: write` or `id-token: write` (red-team #7)
        bad = sorted(scope for scope, v in perms.items()
                     if v == "write" and scope not in _LOW_RISK_WRITE_SCOPES)
        if bad:
            out.append(Finding(
                "CI_TOKEN_OVERPRIVILEGED", P1, path,
                f"workflow grants write on {bad}: exceeds least privilege "
                "(only low-risk write scopes are tolerated)",
                {"write_scopes": bad}))
    on = workflow.get("on") or {}
    dangerous_trigger = "pull_request_target" in (
        on if isinstance(on, (list, dict)) else [on])
    for job_name, job in sorted((workflow.get("jobs") or {}).items()):
        for step in job.get("steps") or []:
            uses = step.get("uses") or ""
            if uses and "@" in uses and not _FULL_SHA.search(uses) \
                    and not uses.startswith("./"):
                out.append(Finding(
                    "DEPENDENCY_NOT_PINNED", P1, f"{path}:{job_name}",
                    f"action {uses!r} not pinned to a full-length commit SHA "
                    "(a mutable tag is not immutable identity, D-0009-42)",
                    {"uses": uses}))
            run = step.get("run") or ""
            if "${{" in run and _ANY_UNTRUSTED_CONTEXT.search(run) \
                    and not _TRUSTED_CONTEXT_FIELDS.search(run):
                m = _ANY_UNTRUSTED_CONTEXT.search(run)
                out.append(Finding(
                    "DANGEROUS_CI_WORKFLOW", P0, f"{path}:{job_name}",
                    f"attacker-influenced context {m.group(0)!r} interpolated "
                    "into a run: script — script injection path (any "
                    "github.event.* not on the trusted allowlist)",
                    {"run": run[:200]}))
            if dangerous_trigger and "actions/checkout" in uses:
                ref = (step.get("with") or {}).get("ref", "")
                if "head" in str(ref) or "github.event.pull_request" in \
                        str(ref):
                    out.append(Finding(
                        "DANGEROUS_CI_WORKFLOW", P0, f"{path}:{job_name}",
                        "privileged pull_request_target workflow checks out "
                        "untrusted PR head: privileged untrusted checkout "
                        "(AC-0009-195)", {"ref": str(ref)}))
    return out


def model_output_findings(usages: list) -> list[Finding]:
    """Model output used as approval / shell / repo write is rejected: an LLM
    may propose; it may never hold authority (INV-0009-40)."""
    out: list[Finding] = []
    for u in usages:
        sink = u.get("sink_kind")
        if u.get("source_kind") == "MODEL_OUTPUT" and sink in \
                ("RELEASE_DECISION", "REPOSITORY_WRITE", "SHELL"):
            out.append(Finding(
                "EXTERNAL_CONTENT_AUTHORITY_REJECTED", P0,
                str(u.get("sink_ref") or "-"),
                f"model output flows directly into {sink}: agent prompt "
                "output cannot become approval or privileged execution "
                "(INV-0009-40, AC-0009-199/200)", {}))
    return out
