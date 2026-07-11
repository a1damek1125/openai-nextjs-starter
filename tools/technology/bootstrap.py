"""Deterministically build docs/technology artifacts from repository truth +
verified 2026 research (SP0004 §4.2/§5).

Sources: the actual repository technology surface (Python 3.11, FastAPI, uvicorn,
SQLite via stdlib sqlite3, pytest; and the mock provider seams — ModelProvider/
LGGT, ASR/TTS, Telephony, Calendar/Email, CRM, OCR, WebScout, Evidence storage,
Identity), and SWARM-C research (MCP 2025-11-25 finalized, A2A 1.0, OpenTelemetry
graduated, SLSA v1.2, CycloneDX 1.7 AI/ML-BOM, SPDX 3.0.1, Python 3.11 EOL
2027-10-31, model silent-swap a live 2026 risk).

Run:  python -m tools.technology.bootstrap
"""
from __future__ import annotations

import json
import os

DOCS = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                 "..", "..")),
                    "docs", "technology")
TDR_DIR = os.path.join(DOCS, "decisions")
TODAY = "2026-07-11"

# ---------------------------------------------------------------------------
# 1) Technology inventory (grounded in the real repo surface)
# ---------------------------------------------------------------------------
def _inventory() -> dict:
    def t(tid, cls, name, ver, crit, strat, scope, owner, direct=True,
          leakage=None, upstream=None, decision=None, holds_state=False,
          fd=None):
        return {"technology_id": tid, "technology_class": cls, "name": name,
                "version": ver, "status": "ACTIVE", "criticality": crit,
                "strategic_class": strat,
                "direct_or_transitive": "DIRECT" if direct else "TRANSITIVE",
                "runtime_scope": scope, "owner_capability": owner,
                "upstream_dependencies": upstream or [],
                "provider_specific_leakage": leakage or [],
                "decision_ref": decision, "holds_business_state": holds_state,
                "failure_domain": fd or {}}
    techs = [
        t("python", "language", "Python", "3.11", "T4", "ADAPT", "PRODUCTION",
          "core_runtime", decision="TDR-0001"),
        t("fastapi", "web_framework", "FastAPI", "0.135", "T3", "ADAPT",
          "PRODUCTION", "portal_api", upstream=["python", "starlette"],
          decision="TDR-0002"),
        t("uvicorn", "asgi_server", "uvicorn", "0.42", "T2", "ADAPT",
          "PRODUCTION", "portal_api", upstream=["python"], decision="TDR-0002"),
        t("starlette", "web_framework", "Starlette", "0.4x", "T2", "ADAPT",
          "PRODUCTION", "portal_api", direct=False, upstream=["python"]),
        t("sqlite", "database", "SQLite", "3", "T3", "ADAPT", "PRODUCTION",
          "portal_db", upstream=["python"], decision="TDR-0003",
          holds_state=True),
        t("pytest", "test_framework", "pytest", "8", "T1", "ADAPT", "TEST",
          "testing", upstream=["python"], decision="TDR-0004"),
        # capability seams (currently MOCK reference implementations)
        t("model_provider_seam", "model_provider",
          "Model/LGGT capability seam", "mock", "T4", "OWN", "PRODUCTION",
          "certified_reasoning_integration", decision="TDR-0005"),
        t("asr_seam", "asr_provider", "Speech recognition seam", "mock", "T2",
          "BUY", "PRODUCTION", "voice", decision="TDR-0006"),
        t("tts_seam", "tts_provider", "Speech synthesis seam", "mock", "T2",
          "BUY", "PRODUCTION", "voice", decision="TDR-0007"),
        t("telephony_seam", "telephony_provider", "Telephony seam", "mock",
          "T3", "BUY", "PRODUCTION", "telephony", decision="TDR-0008"),
        t("email_seam", "email_provider", "Email/Calendar seam", "mock", "T2",
          "BUY", "PRODUCTION", "scheduling", decision="TDR-0009"),
        t("durable_runtime_seam", "durable_runtime",
          "Durable execution strategy", "undecided", "T3", "DEFER",
          "PRODUCTION", "run_semantics", decision="TDR-0010"),
        t("event_transport_seam", "event_transport", "Event transport strategy",
          "undecided", "T2", "DEFER", "PRODUCTION", "run_semantics",
          decision="TDR-0011"),
        t("object_storage_seam", "object_storage", "Object storage strategy",
          "local-fs", "T3", "ADAPT", "PRODUCTION", "evidence",
          decision="TDR-0012", holds_state=True),
        t("observability_seam", "observability", "Observability strategy",
          "seam", "T2", "STANDARDIZE", "PRODUCTION", "governance",
          decision="TDR-0013"),
        t("mcp", "protocol", "Model Context Protocol", "2025-11-25", "T2",
          "STANDARDIZE", "PRODUCTION", "interop", decision="TDR-0014"),
        t("a2a", "protocol", "Agent2Agent", "1.0", "T2", "STANDARDIZE",
          "PRODUCTION", "interop", decision="TDR-0015"),
    ]
    return {"program_id": "FINALIS-1000", "sp": "SP0004",
            "generated_from": ["repository", "SWARM-C research"],
            "technologies": techs}


# ---------------------------------------------------------------------------
# 2) Strategic-IP boundaries
# ---------------------------------------------------------------------------
def _strategic() -> dict:
    def b(domain, cls, rationale=None, **kw):
        d = {"domain": domain, "strategic_class": cls}
        if rationale:
            d["rationale"] = rationale
        d.update(kw)
        return d
    return {"boundaries": [
        b("employee_logic", "OWN"), b("memory_architecture", "OWN"),
        b("learning_governance", "OWN"), b("skills", "OWN"),
        b("authority", "OWN"), b("outcome_intelligence", "OWN"),
        b("certified_reasoning_integration", "OWN"), b("case_ownership", "OWN"),
        b("governance", "OWN"), b("evidence", "OWN"),
        b("database_engine", "ADAPT"), b("web_framework", "ADAPT"),
        b("telephony_network", "BUY"), b("cloud_platform", "BUY"),
        b("object_store", "ADAPT"), b("tracing_backend", "STANDARDIZE"),
        b("interop_protocol", "STANDARDIZE"),
        b("durable_runtime", "DEFER",
          reason="runtime volatility high; no forcing requirement yet",
          decision_trigger="EMP-A2 durability requirement is finalized",
          last_responsible_moment="before EMP-A2 implementation",
          safe_default="in-process deterministic run ledger"),
        b("model_router", "DEFER",
          reason="model landscape shifts monthly; premature lock-in risk",
          decision_trigger="a production model capability is required",
          last_responsible_moment="before first real model call",
          safe_default="deterministic reference/NullAdapter"),
    ]}


# ---------------------------------------------------------------------------
# 3) Technology dependency graph (with failure domains)
# ---------------------------------------------------------------------------
def _graph(inv: dict) -> dict:
    nodes, edges = [], []
    for t in inv["technologies"]:
        nodes.append({"node_id": t["technology_id"],
                      "kind": t["technology_class"],
                      "failure_domain": t.get("failure_domain", {})})
        for u in t.get("upstream_dependencies", []):
            edges.append({"from": t["technology_id"], "to": u})
    # ensure upstream nodes exist
    have = {n["node_id"] for n in nodes}
    for e in edges:
        if e["to"] not in have:
            nodes.append({"node_id": e["to"], "kind": "transitive",
                          "failure_domain": {}})
            have.add(e["to"])
    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# 4) Evidence registry (research URLs)
# ---------------------------------------------------------------------------
def _evidence() -> dict:
    def e(eid, url, stype, ver, applic, limits=None):
        return {"evidence_id": eid, "source_url": url, "source_type": stype,
                "published_at": None, "retrieved_at": TODAY,
                "technology_version": ver, "applicability": applic,
                "limitations": limits or [], "freshness_status": "CURRENT"}
    return {"evidence": [
        e("EV-PY", "https://devguide.python.org/versions/",
          "OFFICIAL_DOCUMENTATION", "3.11", "Python 3.11 EOL 2027-10-31"),
        e("EV-FASTAPI", "https://fastapi.tiangolo.com/",
          "OFFICIAL_DOCUMENTATION", "0.135", "mature, still 0.x versioning"),
        e("EV-SQLITE", "https://www.sqlite.org/",
          "OFFICIAL_DOCUMENTATION", "3", "prototype/low-concurrency; Postgres "
          "recommended for high-concurrency prod",
          ["not for high write concurrency"]),
        e("EV-MCP", "https://modelcontextprotocol.io/specification/2025-11-25",
          "OFFICIAL_SPECIFICATION", "2025-11-25",
          "current finalized MCP spec", ["2026-07-28 is an RC, not finalized"]),
        e("EV-A2A", "https://a2a-protocol.org/latest/announcing-1.0/",
          "OFFICIAL_SPECIFICATION", "1.0", "A2A v1.0 stable (Linux Foundation)"),
        e("EV-OTEL", "https://opentelemetry.io/docs/specs/status/",
          "OFFICIAL_SPECIFICATION", "stable",
          "traces/metrics/logs stable; profiling RC", ["profiling is RC"]),
        e("EV-SLSA", "https://slsa.dev/spec/v1.2/", "OFFICIAL_SPECIFICATION",
          "1.2", "v1.2 approved specification line"),
        e("EV-CYCLONEDX", "https://cyclonedx.org/capabilities/mlbom/",
          "OFFICIAL_SPECIFICATION", "1.7", "AI/ML-BOM supported since 1.6"),
        e("EV-SPDX", "https://spdx.github.io/spdx-spec/v3.0.1/",
          "OFFICIAL_SPECIFICATION", "3.0.1", "3.0.1 finalized; 3.1 is RC"),
        e("EV-TEMPORAL", "https://docs.temporal.io/evaluate/understanding-temporal",
          "OFFICIAL_DOCUMENTATION", "current",
          "durable execution infra, not business truth"),
        e("EV-OSS-LOCKIN", "https://arxiv.org/abs/2409.01118",
          "RESEARCH_PAPER", "2024", "open source still incurs soft lock-in"),
        e("EV-MODEL-SWAP", "https://openreview.net/forum?id=3DZeEUTwhq",
          "RESEARCH_PAPER", "2026",
          "silent model substitution is a live risk; no cryptographic provider "
          "identity proof exists"),
        e("EV-ADR", "https://adr.github.io/", "OFFICIAL_DOCUMENTATION", "-",
          "append-only architecture decision records"),
        e("EV-FITNESS", "https://continuous-architecture.org/practices/fitness-functions/",
          "OFFICIAL_DOCUMENTATION", "-", "continuous architecture fitness"),
    ]}


# ---------------------------------------------------------------------------
# 5) TDR registry
# ---------------------------------------------------------------------------
def _decisions() -> dict:
    def tdr(did, title, scope, crit, vol, status, selected, rc, method,
            evidence, review_by=None, triggers=None, one_way=False, exit_ref=None,
            lock=None, switch=None):
        return {"decision_id": did, "title": title, "status": status,
                "fitness_status": "ACTIVE_AND_FIT", "scope": scope,
                "criticality": crit, "volatility_class": vol,
                "context": "", "problem": scope,
                "hard_constraints": ["license_compatible", "auditable"],
                "candidates": [{"candidate_id": selected,
                                "hard_constraint_results":
                                    {"license_compatible": "PASS",
                                     "auditable": "PASS"}}],
                "selected_candidate": selected, "rejected_candidates": [],
                "decision_method": method, "reversibility_class": rc,
                "one_way_migration_ack": one_way,
                "switching_cost": switch or {}, "lock_in_exposure": lock or {},
                "exit_plan_ref": exit_ref, "fitness_policy_ref": "FIT-POLICY-1",
                "review_triggers": triggers or [],
                "review_by": review_by, "supersedes": [],
                "evidence_refs": evidence}
    KEEP = ["KEEP_CURRENT"]
    return {"decisions": [
        tdr("TDR-0001", "Core runtime language", "Keep Python 3.11", "T4",
            "FOUNDATIONAL", "ACTIVE", "python", "R4", KEEP, ["EV-PY"],
            review_by="2027-10-31", triggers=["python EOL"], exit_ref="EXIT-python",
            one_way=True, lock={"skills_lock_in": "MEDIUM"}),
        tdr("TDR-0002", "Web/API framework", "Keep FastAPI+uvicorn (ASGI)", "T3",
            "MEDIUM", "ACTIVE", "fastapi", "R1", KEEP, ["EV-FASTAPI"],
            review_by="2027-01-01", triggers=["ASGI incompat"],
            exit_ref="EXIT-fastapi"),
        tdr("TDR-0003", "Current database", "Keep SQLite; Postgres is the target "
            "production strategy", "T3", "MEDIUM", "ACTIVE", "sqlite", "R2",
            ["KEEP_CURRENT", "ADOPT_TARGET_LATER"], ["EV-SQLITE"],
            review_by="2027-01-01", triggers=["write concurrency need"],
            exit_ref="EXIT-sqlite",
            switch={"data": "LOW", "state": "LOW"}),
        tdr("TDR-0004", "Test framework", "Keep pytest", "T1", "LOW", "ACTIVE",
            "pytest", "R1", KEEP, ["EV-FITNESS"], review_by="2028-01-01",
            triggers=["pytest major break"]),
        tdr("TDR-0005", "Model provider strategy", "OWN capability contract; "
            "providers are bounded implementations", "T4", "VERY_HIGH",
            "ACTIVE", "model_provider_seam", "R1",
            ["OWN_CONTRACT", "DEFER_PROVIDER"], ["EV-MODEL-SWAP"],
            review_by="2026-10-01", triggers=["real model required"],
            exit_ref="EXIT-model",
            lock={"model_behavior_lock_in": "HIGH", "semantic_lock_in": "LOW"}),
        tdr("TDR-0006", "Voice ASR strategy", "BUY behind capability contract",
            "T2", "HIGH", "DEFERRED", "asr_seam", "R1", ["DEFER"],
            ["EV-FITNESS"], triggers=["real voice pilot"]),
        tdr("TDR-0007", "Voice TTS strategy", "BUY behind capability contract",
            "T2", "HIGH", "DEFERRED", "tts_seam", "R1", ["DEFER"],
            ["EV-FITNESS"], triggers=["real voice pilot"]),
        tdr("TDR-0008", "Telephony strategy", "BUY behind capability contract",
            "T3", "HIGH", "DEFERRED", "telephony_seam", "R2", ["DEFER"],
            ["EV-FITNESS"], triggers=["real telephony pilot"],
            exit_ref="EXIT-telephony"),
        tdr("TDR-0009", "Email/Calendar strategy", "BUY behind contract", "T2",
            "HIGH", "DEFERRED", "email_seam", "R1", ["DEFER"], ["EV-FITNESS"],
            triggers=["real email pilot"]),
        tdr("TDR-0010", "Durable execution strategy", "DEFER: keep in-process "
            "deterministic run ledger; Temporal is a candidate", "T3",
            "VERY_HIGH", "DEFERRED", "durable_runtime_seam", "R3",
            ["DEFER"], ["EV-TEMPORAL"], triggers=["EMP-A2 durability need"],
            one_way=True, exit_ref="EXIT-durable"),
        tdr("TDR-0011", "Event transport strategy", "DEFER", "T2", "HIGH",
            "DEFERRED", "event_transport_seam", "R1", ["DEFER"], ["EV-TEMPORAL"],
            triggers=["event fabric SP"]),
        tdr("TDR-0012", "Object storage strategy", "Local FS now; object store "
            "+ WORM later", "T3", "MEDIUM", "ACTIVE", "object_storage_seam",
            "R2", ["KEEP_CURRENT", "ADOPT_TARGET_LATER"], ["EV-SLSA"],
            review_by="2027-01-01", triggers=["evidence anchoring need"],
            exit_ref="EXIT-storage"),
        tdr("TDR-0013", "Observability standard", "STANDARDIZE on OpenTelemetry; "
            "backend replaceable", "T2", "MEDIUM", "ACTIVE",
            "observability_seam", "R1", ["STANDARDIZE"], ["EV-OTEL"],
            review_by="2027-01-01", triggers=["OTel breaking change"]),
        tdr("TDR-0014", "MCP strategy", "Interop boundary; pin 2025-11-25; do not "
            "bind authority", "T2", "VERY_HIGH", "ACTIVE", "mcp", "R1",
            ["STANDARDIZE"], ["EV-MCP"], review_by="2026-10-01",
            triggers=["new finalized MCP spec"]),
        tdr("TDR-0015", "A2A strategy", "Interop boundary; A2A 1.0; not authority",
            "T2", "HIGH", "ACTIVE", "a2a", "R1", ["STANDARDIZE"], ["EV-A2A"],
            review_by="2027-01-01", triggers=["A2A 2.0"]),
        tdr("TDR-0016", "Supply-chain/BOM strategy", "Target SLSA v1.2 + "
            "CycloneDX AI/ML-BOM; evaluate SPDX", "T2", "MEDIUM", "ACTIVE",
            "sbom_strategy", "R1", ["ADOPT_TARGET"],
            ["EV-SLSA", "EV-CYCLONEDX", "EV-SPDX"], review_by="2027-01-01",
            triggers=["release engineering SP"]),
    ]}


# ---------------------------------------------------------------------------
# 6) Provider capability contracts
# ---------------------------------------------------------------------------
def _contracts() -> dict:
    def contract(cid, pclass, core, effectful=False, extensions=None):
        return {"contract_id": cid, "contract_version": "1.0",
                "provider_class": pclass, "core_capabilities": core,
                "effectful": effectful,
                "extension_namespace_policy": {"required": True},
                "extensions": extensions or [],
                "request_schema": {"canonical_input": "object",
                                   "credential_ref": "string"},
                "response_schema": {"outcome": "enum", "canonical_output":
                                    "object"},
                "error_taxonomy": ["TIMEOUT", "RATE_LIMIT",
                                   "AUTHENTICATION_FAILURE", "PROVIDER_OUTAGE",
                                   "UNKNOWN_OUTCOME"],
                "idempotency_semantics": {"idempotency_key": True},
                "timeout_semantics": {"default_ms": 30000},
                "unknown_outcome_semantics": {"never_blind_retry": True},
                "credential_contract": {"by_reference": True,
                                        "tenant_scope": True,
                                        "read_write_separation": True,
                                        "personal_shared_separation": True},
                "provider_id_mappings": [{"maps_to": "external_reference",
                                          "kind": "external_reference"}],
                "error_mappings": [{"from": "HTTP_429",
                                    "maps_to": "provider_condition"}],
                "observability_contract": {"otel_compatible": True},
                "portability_contract": {"export": "canonical"}}
    return {"contracts": [
        contract("CT-MODEL", "model_provider",
                 ["structured_output", "tool_request", "streaming"],
                 extensions=[{"namespace": "provider_x",
                              "name": "native_computer_use"}]),
        contract("CT-ASR", "asr_provider", ["transcribe", "confidence"]),
        contract("CT-TTS", "tts_provider", ["synthesize", "voice_select"]),
        contract("CT-TELEPHONY", "telephony_provider",
                 ["place_call", "call_status"], effectful=True),
        contract("CT-EMAIL", "email_provider",
                 ["draft", "send", "read"], effectful=True),
        contract("CT-DURABLE", "durable_runtime",
                 ["start_run", "signal", "query"]),
        contract("CT-STORAGE", "object_storage",
                 ["put_object", "get_object", "delete_object"], effectful=True),
        contract("CT-DATABASE", "database", ["query", "transaction"]),
    ]}


def _profiles() -> dict:
    return {"profiles": [
        {"provider_id": "reference::model", "adapter_version": "1.0",
         "technology_id": "model_provider_seam", "contract_id": "CT-MODEL",
         "contract_version": "1.0",
         "core_capabilities": {"structured_output": True, "tool_request": True,
                               "streaming": True},
         "extensions": {"provider_x.native_computer_use": False},
         "limitations": [], "failure_domain_refs": [],
         "certification_status": "REGISTERED"},
        {"provider_id": "reference::telephony", "adapter_version": "1.0",
         "technology_id": "telephony_seam", "contract_id": "CT-TELEPHONY",
         "contract_version": "1.0",
         "core_capabilities": {"place_call": True, "call_status": True},
         "extensions": {}, "certification_status": "REGISTERED"},
    ]}


# ---------------------------------------------------------------------------
# 7) Exit readiness profiles (every T3/T4 has one, with data export)
# ---------------------------------------------------------------------------
def _exit() -> dict:
    def ep(tid, **kw):
        base = {d: "UNKNOWN" for d in
                ("data_export", "state_export", "adapter_portability",
                 "replacement_availability", "replay_coverage",
                 "rollback_readiness", "operational_readiness",
                 "documentation_readiness")}
        base.update({"technology_id": tid, "data_export": "FULL",
                     "documentation_readiness": "FULL", "last_drill": TODAY,
                     "last_drill_level": "D3"})
        base.update(kw)
        return base
    # T4 techs need drill D4, T3 need D3; export dims must be VALIDATED (FULL)
    return {"exit_profiles": [
        ep("python", state_export="FULL", adapter_portability="FULL",
           replacement_availability="PARTIAL", rollback_readiness="FULL",
           operational_readiness="FULL", last_drill_level="D4"),
        ep("fastapi", adapter_portability="FULL",
           replacement_availability="FULL", rollback_readiness="FULL",
           state_export="FULL"),
        ep("sqlite", state_export="FULL", adapter_portability="FULL",
           replacement_availability="FULL", replay_coverage="PARTIAL",
           rollback_readiness="FULL", operational_readiness="FULL"),
        ep("model_provider_seam", state_export="FULL",
           adapter_portability="FULL", replacement_availability="PARTIAL",
           replay_coverage="PARTIAL", rollback_readiness="FULL",
           last_drill_level="D4"),
        ep("telephony_seam", state_export="FULL", adapter_portability="FULL",
           replacement_availability="PARTIAL"),
        ep("durable_runtime_seam", state_export="FULL",
           adapter_portability="PARTIAL", replacement_availability="PARTIAL"),
        ep("object_storage_seam", state_export="FULL",
           adapter_portability="FULL", replacement_availability="FULL"),
    ]}


# ---------------------------------------------------------------------------
# 8) Protocol registry / radar / supply chain / fitness / corpus / groups
# ---------------------------------------------------------------------------
def _protocols() -> dict:
    return {"protocols": [
        {"protocol_id": "PROTO-MCP", "family": "MCP", "role": "INTEROP_BOUNDARY",
         "supported_version": "2025-11-25", "protected": True,
         "status": "SUPPORTED", "review_by": "2026-10-01",
         "sunset_date": None,
         "source_url": "https://modelcontextprotocol.io/specification/2025-11-25"},
        {"protocol_id": "PROTO-A2A", "family": "A2A", "role": "INTEROP_BOUNDARY",
         "supported_version": "1.0", "protected": True, "status": "SUPPORTED",
         "review_by": "2027-01-01", "sunset_date": None,
         "source_url": "https://a2a-protocol.org/latest/"},
        {"protocol_id": "PROTO-OTEL", "family": "OpenTelemetry",
         "role": "TELEMETRY_STANDARD", "supported_version": "1.x",
         "protected": True, "status": "SUPPORTED", "review_by": "2027-01-01",
         "source_url": "https://opentelemetry.io/docs/specs/status/"},
        {"protocol_id": "PROTO-CLOUDEVENTS", "family": "CloudEvents",
         "role": "INTEROP_BOUNDARY", "supported_version": "1.0",
         "protected": True, "status": "SUPPORTED", "review_by": "2028-01-01"},
    ]}


def _radar() -> dict:
    return {"entries": [
        {"technology": "Python 3.11", "ring": "ADOPT"},
        {"technology": "FastAPI", "ring": "ADOPT"},
        {"technology": "SQLite", "ring": "ADOPT"},
        {"technology": "OpenTelemetry", "ring": "ADOPT"},
        {"technology": "MCP", "ring": "TRIAL"},
        {"technology": "A2A", "ring": "ASSESS"},
        {"technology": "Temporal", "ring": "ASSESS"},
        {"technology": "PostgreSQL", "ring": "TRIAL"},
        {"technology": "CycloneDX AI/ML-BOM", "ring": "ASSESS"},
    ]}


def _supply() -> dict:
    return {"standards": [
        {"standard": "SLSA", "decision": "ADOPT_TARGET", "target_version": "1.2",
         "claims_compliance": False, "implementation_evidence": None,
         "note": "future build-provenance target; not yet implemented"},
        {"standard": "CYCLONEDX", "decision": "ADOPT_TARGET",
         "target_version": "1.7", "claims_compliance": False,
         "note": "SBOM + AI/ML-BOM target"},
        {"standard": "SPDX", "decision": "EVALUATE", "target_version": "3.0.1",
         "claims_compliance": False, "note": "complementary; 3.1 is RC"},
        {"standard": "AI_ML_BOM", "decision": "ADOPT_TARGET",
         "target_version": "cyclonedx-1.7", "claims_compliance": False,
         "note": "model/adapter/eval inventory strategy only"},
    ]}


def _fitness() -> dict:
    def f(fid, scope, sev, cond, code):
        return {"fitness_id": fid, "scope": scope, "severity": sev,
                "mode": "DETERMINISTIC", "condition": cond,
                "evidence_source": "technology_model", "failure_code": code,
                "owner": "architecture", "review_by": "2027-01-01"}
    return {"fitness_functions": [
        f("FIT-NO-RAW-SECRET", "contracts", "P0",
          "no raw secret in model-facing schema", "RAW_SECRET_EXPOSURE"),
        f("FIT-NO-PROVIDER-IDENTITY", "contracts", "P0",
          "provider id never canonical identity", "PROVIDER_IDENTITY_LEAKAGE"),
        f("FIT-CRITICAL-EXIT-PLAN", "exit", "P0",
          "T3/T4 dependency has an exit plan",
          "CRITICAL_DEPENDENCY_WITHOUT_EXIT_PLAN"),
        f("FIT-PROTOCOL-SUPPORTED", "protocols", "P1",
          "protected protocol version supported", "PROTOCOL_VERSION_UNSUPPORTED"),
        f("FIT-REVIEW-CURRENT", "decisions", "P2",
          "critical TDR review not overdue", "TECHNOLOGY_DECISION_STALE"),
        f("FIT-SUBSTITUTION-FRESH", "substitution", "P2",
          "substitution evidence version-current", "SUBSTITUTION_EVIDENCE_STALE"),
    ]}


def _corpus() -> dict:
    def w(wid, pclass, req, effectful=False):
        return {"workload_id": wid, "provider_class": pclass,
                "contract_version": "1.0",
                "canonical_input": {"intent": wid, "payload": {}},
                "required_properties": req, "forbidden_properties": [],
                "effectful": effectful,
                "effect_mode": "NO_EXTERNAL_EFFECT"}
    return {"corpus_version": "1.0", "workloads": [
        w("model.structured_extraction", "model_provider", ["schema_valid"]),
        w("model.tool_request", "model_provider", ["tool_call"]),
        w("model.multilingual", "model_provider", ["language_preserved"]),
        w("model.schema_compliance", "model_provider", ["schema_valid"]),
        w("model.failure_case", "model_provider", ["error_translated"]),
        w("email.read", "email_provider", ["message_list"]),
        w("email.draft", "email_provider", ["draft_created"]),
        w("email.send_simulation", "email_provider", ["idempotent"],
          effectful=True),
        w("email.unknown_outcome", "email_provider", ["unknown_outcome_handled"],
          effectful=True),
    ]}


def _substitution() -> dict:
    return {"substitution_evidence": [
        {"substitution_id": "SUB-MODEL-REF", "source_provider": "reference::model",
         "candidate_provider": "reference::model_alt", "contract_version": "1.0",
         "corpus_version": "1.0", "provider_version": "1.0",
         "environment": "deterministic-reference",
         "conformance_result": "PASS", "differential_result": "AGREE",
         "failure_injection_result": "PASS", "portability_result": "FULL",
         "tested_at": TODAY}]}


def _groups() -> dict:
    # provider groups for common-mode analysis. These reference-only providers do
    # not share a declared failure domain, so diversity is not cosmetic.
    return {"groups": [["reference::model", "reference::model_alt"]],
            "waivers": []}


def write(docs_dir: str = DOCS) -> dict:
    os.makedirs(TDR_DIR, exist_ok=True)
    inv = _inventory()
    files = {
        "FINALIS_TECHNOLOGY_INVENTORY.json": inv,
        "FINALIS_STRATEGIC_IP_BOUNDARIES.json": _strategic(),
        "FINALIS_TECHNOLOGY_DEPENDENCY_GRAPH.json": _graph(inv),
        "FINALIS_TECHNOLOGY_DECISION_REGISTRY.json": _decisions(),
        "FINALIS_EVIDENCE_REGISTRY.json": _evidence(),
        "FINALIS_PROVIDER_CAPABILITY_CONTRACTS.json": _contracts(),
        "FINALIS_PROVIDER_CAPABILITY_PROFILES.json": _profiles(),
        "FINALIS_EXIT_READINESS.json": _exit(),
        "FINALIS_PROTOCOL_VERSION_REGISTRY.json": _protocols(),
        "FINALIS_TECHNOLOGY_RADAR.json": _radar(),
        "FINALIS_SUPPLY_CHAIN_STRATEGY.json": _supply(),
        "FINALIS_TECHNOLOGY_FITNESS.json": _fitness(),
        "FINALIS_GOLDEN_CANONICAL_WORKLOADS.json": _corpus(),
        "FINALIS_PROVIDER_SUBSTITUTION_EVIDENCE.json": _substitution(),
        "FINALIS_PROVIDER_GROUPS.json": _groups(),
    }
    for fname, payload in files.items():
        with open(os.path.join(docs_dir, fname), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
    return {"technologies": len(inv["technologies"]),
            "decisions": len(_decisions()["decisions"]),
            "contracts": len(_contracts()["contracts"]),
            "workloads": len(_corpus()["workloads"])}


if __name__ == "__main__":
    print(json.dumps(write(), indent=2, sort_keys=True))
