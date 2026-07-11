"""Canonical concept definitions for the Finalis Semantic Constitution.

Discovered from repository evidence (see FINALIS_SEMANTIC_COLLISION_REPORT.md),
then canonicalized — never invented (SP0002 §8). `bootstrap.py` renders these into
FINALIS_CANONICAL_CONCEPT_REGISTRY.json with computed Meaning Hashes.

Identity is a FIXED opaque brand-independent id (`c-NNNN`), immutable and never
reused (INV-0002-01, D-0002-02/03) — deliberately NOT derived from canonical_key
so a key rename never changes identity (INV-0002-03: label != identity).
"""
from __future__ import annotations

# owner capabilities reference the SP0001 architecture twin capability ids.
def C(cid, key, kind, owner, definition, *, world="PARTIAL_WORLD",
      epistemic=None, invariants=None, authority=None, temporal=None,
      state=None, rels=None, labels=None, aliases=None, deprecated=None,
      forbidden=None, status="ACTIVE", projections=None):
    return {
        "concept_id": cid,
        "canonical_key": key,
        "concept_kind": kind,
        "owner_capability": owner,
        "semantic_revision": 1,
        "status": status,
        "normative_definition": definition,
        "world_assumption": world,
        "epistemic_rules": epistemic or [],
        "semantic_invariants": invariants or [],
        "authority_semantics": authority or [],
        "temporal_semantics": temporal or {},
        "state_semantics": state or {},
        "relationships": rels or [],
        "labels": labels or {},
        "aliases": aliases or [],
        "deprecated_aliases": deprecated or [],
        "forbidden_aliases": forbidden or [],
        "projection_refs": projections or {},
    }


def _L(en, pl, de, es):
    return {"en": en, "pl": pl, "de": de, "es": es}


CONCEPTS = [
    # -- work --------------------------------------------------------------
    C("c-0001", "work.task", "ENTITY", "core_a2_tasks",
      "A canonical Task Contract admitted by the Secure Work Intake Registry "
      "(CORE-A2): a bounded, specified unit of requested work. NOT the same as an "
      "Owned Work item.",
      rels=[{"type": "PRECEDES", "target": "work.owned_work"}],
      labels=_L("Task", "Zadanie", "Aufgabe", "Tarea"),
      aliases=["ai_task"], forbidden=["owned_work", "work_item"]),
    C("c-0002", "work.owned_work", "ENTITY", "emp_a1_work_inbox",
      "An admitted, owned unit of work the Employee OS owns over time (EMP-A1 work "
      "item): has an owner and a next-action/wait/blocker/completion. Distinct "
      "from a CORE-A2 Task Contract.",
      world="PARTIAL_WORLD",
      invariants=["Active(owned_work) => Owner AND (NextAction OR Wait OR Blocker "
                  "OR Completion)  [SP0000 Zero-Lost-Work]"],
      labels=_L("Owned Work", "Praca własna", "Eigene Arbeit", "Trabajo propio"),
      aliases=["work_item"], forbidden=["task"]),
    C("c-0003", "work.wait_condition", "STATE", "emp_a1_work_inbox",
      "An explicit condition an owned work item is waiting on (time, human, "
      "external signal). A wait is not a blocker and not a failure.",
      labels=_L("Wait Condition", "Warunek oczekiwania", "Wartebedingung",
                "Condición de espera")),
    C("c-0004", "work.blocker", "STATE", "emp_a1_work_inbox",
      "An explicit impediment preventing progress on owned work. Distinct from a "
      "wait condition (expected) and from completion.",
      labels=_L("Blocker", "Blokada", "Blocker", "Bloqueo")),

    # -- case / run --------------------------------------------------------
    C("c-0005", "case.case", "ENTITY", "case_graph",
      "A Case Graph case: the business matter being worked, with missing-info, "
      "promises and next-best-action. NOT a Run.",
      labels=_L("Case", "Sprawa", "Fall", "Caso"),
      forbidden=["run"]),
    C("c-0006", "run.run", "ENTITY", "core_a3_run_ledger",
      "A causally-verifiable, event-sourced execution record in the Run Ledger "
      "(CORE-A3). A run terminating is NOT a business outcome.",
      rels=[{"type": "PRODUCES", "target": "event.event"}],
      labels=_L("Run", "Przebieg", "Lauf", "Ejecución"),
      forbidden=["case", "completed"]),
    C("c-0007", "event.event", "EVENT", "agent_runtime_governance",
      "An immutable recorded occurrence with stable identity, tenant scope and a "
      "semantic epoch reference; interpreted under the epoch active at occurrence.",
      temporal={"bitemporal": True, "interpret_under": "occurrence_epoch"},
      labels=_L("Event", "Zdarzenie", "Ereignis", "Evento")),

    # -- action / effect / outcome / completion (the 'completed' family) ---
    C("c-0008", "action.action", "EVENT", "action_communication",
      "An ATTEMPTED operation (e.g. send message, dial). An action attempted is "
      "not an effect achieved and not an outcome. EMAIL_SENT != CUSTOMER_RESPONDED.",
      rels=[{"type": "PRECEDES", "target": "effect.effect"}],
      labels=_L("Action", "Akcja", "Aktion", "Acción"),
      forbidden=["completed", "effect", "outcome"]),
    C("c-0009", "effect.effect", "STATE", "tool_b9_local_transaction",
      "A concrete change of state produced by executing an action (real or, in the "
      "current closed-effect system, simulated/inert). An effect is not the "
      "business outcome. INVOICE_SENT != PAYMENT_RECEIVED.",
      world="CLOSED_WORLD",
      rels=[{"type": "PRECEDES", "target": "outcome.business_outcome"}],
      labels=_L("Effect", "Efekt", "Effekt", "Efecto"),
      forbidden=["completed", "action", "outcome"]),
    C("c-0010", "outcome.business_outcome", "STATE", "lifecycle_universal",
      "A verified business result (e.g. deal WON, payment received). Under bounded "
      "scope, not-verified => not achieved (CLOSED_WORLD). Distinct from activity, "
      "effect and formal completion.",
      world="CLOSED_WORLD",
      epistemic=["requires ADMITTED_FACT or CERTIFIED_CONCLUSION to assert achieved"],
      labels=_L("Business Outcome", "Wynik biznesowy", "Geschäftsergebnis",
                "Resultado de negocio"),
      forbidden=["completed", "activity", "effect"]),
    C("c-0011", "lifecycle.completion", "STATE", "lifecycle_universal",
      "The formal completion predicate of the Universal Lifecycle: an explicit, "
      "bounded rule over invariants. Completion is a proven predicate, not a UI "
      "click or a dispatched message.",
      world="CLOSED_WORLD",
      invariants=["completion is a predicate over lifecycle invariants, not a "
                  "provider/UI/model assertion"],
      labels=_L("Completion", "Ukończenie", "Abschluss", "Finalización"),
      forbidden=["completed", "closed_by_user", "message_sent"]),

    # -- epistemic: claim / fact / evidence / artifact ---------------------
    C("c-0012", "evidence.claim", "ARTIFACT", "core_a6_artifacts",
      "An assertion carrying an explicit epistemic status. A claim is NOT a fact. "
      "An LLM/model output enters only as a CLAIM (never ADMITTED_FACT directly).",
      epistemic=["SIGNAL", "OBSERVATION", "CLAIM", "CORROBORATED_CLAIM"],
      invariants=["CLAIM != ADMITTED_FACT (INV-0002-05)",
                  "LLM output admits only as CLAIM (INV-0002-13)"],
      labels=_L("Claim", "Twierdzenie", "Behauptung", "Afirmación"),
      forbidden=["fact", "verified"]),
    C("c-0013", "evidence.fact", "STATE", "evidence",
      "An ADMITTED_FACT: an assertion that has passed a defined admission process "
      "(evidence-bound). A fact is not automatically an external-world truth and "
      "not an execution authority.",
      epistemic=["ADMITTED_FACT"],
      world="PARTIAL_WORLD",
      invariants=["admission requires a defined process, not a model guess",
                  "ADMITTED_FACT != CERTIFIED_CONCLUSION != AUTHORITY"],
      labels=_L("Fact", "Fakt", "Fakt", "Hecho"),
      forbidden=["claim", "guess", "assumption"]),
    C("c-0014", "evidence.evidence", "ENTITY", "evidence",
      "An evidence object in the Evidence Trust Fabric: content with chain, "
      "provenance, holds and proof reports. Evidence supports claims/facts; it is "
      "not itself a claim or an artifact.",
      labels=_L("Evidence", "Dowód", "Nachweis", "Evidencia"),
      forbidden=["artifact", "claim"]),
    C("c-0015", "artifact.artifact", "ARTIFACT", "core_a6_artifacts",
      "An evidence-grade produced artifact in the Claim Graph (CORE-A6) behind a "
      "materialization firewall. Distinct from evidence (input) and claim "
      "(assertion).",
      labels=_L("Artifact", "Artefakt", "Artefakt", "Artefacto"),
      forbidden=["evidence"]),

    # -- approval / authority / permission ---------------------------------
    C("c-0016", "approval.approval", "ENTITY", "core_a4_approvals",
      "A human approval decision producing a bounded, non-transferable, consumable "
      "grant (CORE-A4). An approval artifact is not an unlimited execution right.",
      authority=["bounded", "non_transferable", "single_use / consume-checked"],
      labels=_L("Approval", "Zatwierdzenie", "Genehmigung", "Aprobación")),
    C("c-0017", "authority.authority", "RELATION", "core_a1_identity",
      "The right to authorize an effect within the governance chain. Authority "
      "lives only in the Finalis governance chain; model output, external content, "
      "certified conclusions and the frontend are never authority.",
      authority=["narrows down the ladder, never widens"],
      invariants=["MODEL_OUTPUT/EXTERNAL_CONTENT/CERTIFIED/FRONTEND != AUTHORITY "
                  "(SP0000 INV-0000-02..05)"],
      labels=_L("Authority", "Uprawnienie władcze", "Autorität", "Autoridad"),
      forbidden=["permission", "capability"]),
    C("c-0018", "authority.permission", "RELATION", "rbac_admin",
      "An RBAC grantable permission (deny-by-default catalog). A permission is a "
      "policy grant, distinct from governance authority and from a tool.",
      labels=_L("Permission", "Pozwolenie", "Berechtigung", "Permiso"),
      aliases=["rbac_permission"], forbidden=["authority", "capability", "tool"]),

    # -- tool / skill / capability -----------------------------------------
    C("c-0019", "tool.tool", "ENTITY", "tool_b1_registry",
      "A governed tool capability admitted by the Zero-Trust Tool Registry "
      "(TOOL-B1). A tool is not a skill and not an RBAC permission and not an "
      "SP0001 architecture capability.",
      labels=_L("Tool", "Narzędzie", "Werkzeug", "Herramienta"),
      forbidden=["skill", "capability", "permission"]),
    C("c-0020", "skill.skill", "ENTITY", "emp_a1_work_inbox",
      "A composable, versioned procedure/SOP the Employee OS can apply (strategic "
      "Finalis IP; FUTURE — not yet implemented in the repo). A skill orchestrates "
      "tools; it is not itself a tool.",
      status="PROPOSED",
      labels=_L("Skill", "Umiejętność", "Fähigkeit", "Habilidad"),
      forbidden=["tool"]),
    C("c-0021", "capability.architecture_capability", "RELATION", "portal_shell",
      "SP0001 architecture-twin capability: an OWNERSHIP unit of code, NOT a "
      "business-domain concept. It must never be used as a business alias for tool "
      "or permission (cross-SP collision guard).",
      status="ACTIVE",
      invariants=["architecture capability is a projection of SP0001, not a "
                  "business concept"],
      labels=_L("Architecture Capability", "Zdolność architektury",
                "Architektur-Fähigkeit", "Capacidad de arquitectura"),
      forbidden=["tool", "permission", "skill"]),

    # -- provider ----------------------------------------------------------
    C("c-0022", "provider.provider", "ENTITY", "action_communication",
      "An external execution provider (telephony/email/calendar/LLM/etc.), "
      "currently mocked. A provider's vocabulary is external and must map through "
      "an anti-corruption adapter; it never becomes internal semantic authority.",
      world="OPEN_WORLD",
      invariants=["EXTERNAL_PROTOCOL != INTERNAL_SEMANTIC_AUTHORITY (INV-0002-09)"],
      labels=_L("Provider", "Dostawca", "Anbieter", "Proveedor")),

    # -- employee / worker / agent -----------------------------------------
    C("c-0023", "employee.employee", "ROLE", "core_a1_identity",
      "The single user-facing AI Employee identity (CORE-A1). One employee may use "
      "many internal specialist workers, but Owned Work has one ownership model.",
      invariants=["one user-facing employee, many internal workers (SP0000 "
                  "INV-0000-06)"],
      labels=_L("Employee", "Pracownik", "Mitarbeiter", "Empleado"),
      aliases=["ai_employee"], forbidden=["worker", "agent"]),
    C("c-0024", "employee.worker", "ROLE", "rbac_admin",
      "An internal specialist worker (bounded capabilities, possibly a different "
      "model). A worker is an internal actor, not the user-facing employee and not "
      "a generic agent.",
      labels=_L("Worker", "Specjalista", "Fachkraft", "Especialista"),
      aliases=["ai_worker"], forbidden=["employee", "agent"]),
    C("c-0025", "employee.agent", "ROLE", "agent_runtime_governance",
      "A generic autonomous agent process. Distinct from the Finalis Employee "
      "identity and from an internal worker.",
      labels=_L("Agent", "Agent", "Agent", "Agente"),
      forbidden=["employee", "worker"]),

    # -- memory / experience -----------------------------------------------
    C("c-0026", "memory.memory", "ENTITY", "crm",
      "Governed memory: facts/preferences/relationship context with provenance and "
      "temporal validity. Memory is data, never authority; tenant-scoped.",
      world="OPEN_WORLD",
      labels=_L("Memory", "Pamięć", "Gedächtnis", "Memoria")),
    C("c-0027", "memory.experience", "ENTITY", "agent_runtime_governance",
      "A captured outcome-attributed experience feeding controlled learning "
      "(FUTURE). Experience yields candidate lessons via a gated pipeline, never "
      "direct production mutation.",
      status="PROPOSED",
      labels=_L("Experience", "Doświadczenie", "Erfahrung", "Experiencia")),

    # -- promise / commitment ----------------------------------------------
    C("c-0028", "relationship.promise", "STATE", "crm",
      "A stated intention to do something (tracked by the PromiseTracker). A "
      "promise is a CLAIM-level intention, not a verified commitment.",
      epistemic=["CLAIM", "CORROBORATED_CLAIM"],
      labels=_L("Promise", "Obietnica", "Versprechen", "Promesa"),
      forbidden=["commitment"]),
    C("c-0029", "relationship.commitment", "STATE", "crm",
      "A verified, corroborated obligation. A commitment carries a higher "
      "epistemic status than a promise; the two must not be conflated.",
      epistemic=["CORROBORATED_CLAIM", "ADMITTED_FACT"],
      labels=_L("Commitment", "Zobowiązanie", "Verpflichtung", "Compromiso"),
      forbidden=["promise"]),

    # -- party / customer --------------------------------------------------
    C("c-0030", "party.party", "ENTITY", "crm",
      "A party in the Relationship Core: person or organization. Supertype of "
      "customer.",
      rels=[],
      labels=_L("Party", "Strona", "Partei", "Parte")),
    C("c-0031", "party.customer", "ENTITY", "crm",
      "A party in a commercial relationship. A customer IS_A party.",
      rels=[{"type": "IS_A", "target": "party.party"}],
      labels=_L("Customer", "Klient", "Kunde", "Cliente")),

    # -- language ----------------------------------------------------------
    C("c-0032", "language.control_language", "ROLE", "rbac_admin",
      "The language in which a human controls Finalis. Independent of the work "
      "language; control language never defines business semantics (SP0000 "
      "INV-0000-12).",
      invariants=["control language must not define business semantics"],
      labels=_L("Control Language", "Język sterowania", "Steuersprache",
                "Idioma de control"),
      forbidden=["work_language"]),
    C("c-0033", "language.work_language", "ROLE", "action_communication",
      "The language in which work is performed with a customer. Independent of the "
      "control language; a label/translation cannot change business meaning.",
      invariants=["translation cannot redefine semantics (INV-0002-08)"],
      labels=_L("Work Language", "Język pracy", "Arbeitssprache",
                "Idioma de trabajo"),
      forbidden=["control_language"]),
]

# Concepts referenced as relationship targets must resolve — keyed for checks.
CONCEPT_KEYS = {c["canonical_key"] for c in CONCEPTS}
