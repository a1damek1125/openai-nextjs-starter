"""Shared fixtures for the Human Approval Gate PART 2 (CORE-A4.2) tests.

The `gate` fixture builds a seeded app with a SECOND owner in the demo tenant
so separation-of-duties can be exercised: a request created by the manager is
decided by an owner who is not the requester.
"""
import pytest
from fastapi.testclient import TestClient

from finalis.portal.app import create_app
from finalis.portal.auth import AuthService
from finalis.portal.seed import seed

OWNER = "owner@demo.finalis"
OWNER2 = "owner2@demo.finalis"
MANAGER = "manager@demo.finalis"
VIEWER = "viewer@demo.finalis"
OTHER_OWNER = "owner@other.finalis"


class Gate:
    def __init__(self):
        self.app = create_app(":memory:")
        seed(self.app.state.db)
        self.c = TestClient(self.app)
        self.tid = self.db.one("SELECT tenant_id FROM users WHERE email=?",
                               OWNER)["tenant_id"]
        AuthService(self.db).create_user(
            tenant_id=self.tid, email=OWNER2, password="demo1234", role="owner")

    @property
    def db(self):
        return self.app.state.db

    def add_user(self, email, role):
        AuthService(self.db).create_user(
            tenant_id=self.tid, email=email, password="demo1234", role=role)

    def h(self, email=OWNER):
        tok = self.c.post("/auth/login", json={
            "email": email, "password": "demo1234"}).json()["token"]
        return {"Authorization": "Bearer " + tok}

    def case_id(self, hdr=None):
        return self.c.get("/cases", headers=hdr or self.h()).json()[0]["id"]

    def make_request(self, task_type="customer_reply_draft",
                     requester=MANAGER):
        hdr = self.h(requester)
        cid = self.case_id(hdr)
        tk = self.c.post("/ai-tasks", json={
            "task_type": task_type, "task_title": "t",
            "task_description": "please do the thing", "subject_type": "case",
            "subject_id": cid}, headers=hdr).json()
        run = self.c.post("/ai-runs", json={"task_id": tk["task_id"]},
                          headers=hdr).json()
        ap = self.c.post("/ai-approvals", json={"run_id": run["run_id"]},
                         headers=hdr).json()
        return ap, run["run_id"]

    def approve(self, ap, approver=OWNER2, challenge=True, acks=None,
                viewed=None, reason="ok"):
        aid = ap["approval_request_id"]
        required = ap["policy_decision_capsule"]["required_acknowledgements"]
        if acks is None:
            acks = {a: True for a in required}
        body = {"viewed_package_hash": (viewed if viewed is not None
                                        else ap["approval_package_hash"]),
                "acknowledgements": acks, "challenge_passed": challenge,
                "decision_reason": reason}
        return self.c.post(f"/ai-approvals/{aid}/approve", json=body,
                           headers=self.h(approver))

    def set_request_field(self, aid, **fields):
        """White-box helper: patch stored request payload fields (e.g. force a
        dual-control quorum) to exercise a code path directly."""
        import json
        row = self.db.one(
            "SELECT payload_json FROM ai_approval_requests WHERE id=?", aid)
        p = json.loads(row["payload_json"])
        p.update(fields)
        self.db.conn.execute(
            "UPDATE ai_approval_requests SET payload_json=? WHERE id=?",
            (json.dumps(p), aid))
        self.db.conn.commit()

    def raw_approve(self, aid, ap, approver, challenge=True):
        acks = {a: True for a in ap["policy_decision_capsule"][
            "required_acknowledgements"]}
        return self.c.post(f"/ai-approvals/{aid}/approve", json={
            "viewed_package_hash": ap["approval_package_hash"],
            "acknowledgements": acks, "challenge_passed": challenge},
            headers=self.h(approver))

    def grant(self, aid, approver=OWNER2):
        return self.c.get(f"/ai-approvals/{aid}/grant", headers=self.h(
            approver)).json()

    def consume_check(self, aid, approver=OWNER2):
        return self.c.post(f"/ai-approvals/{aid}/consume-check",
                           headers=self.h(approver)).json()

    # -- CORE-A5 lifecycle helpers --------------------------------------------
    def make_task(self, task_type="case_summary", requester=MANAGER,
                  subject=True):
        hdr = self.h(requester)
        cid = self.case_id(hdr)
        body = {"task_type": task_type, "task_title": "t",
                "task_description": "please do the thing"}
        if subject:
            body.update(subject_type="case", subject_id=cid)
        return self.c.post("/ai-tasks", json=body, headers=hdr).json()[
            "task_id"]

    def lc_state(self, task_id, actor=OWNER):
        return self.c.get(f"/ai-tasks/{task_id}/state",
                          headers=self.h(actor)).json()

    def transition(self, task_id, event, actor=OWNER, **body):
        body["transition_event"] = event
        return self.c.post(f"/ai-tasks/{task_id}/transitions", json=body,
                           headers=self.h(actor))

    def dry_run(self, task_id, event, actor=OWNER, **body):
        body["transition_event"] = event
        return self.c.post(f"/ai-tasks/{task_id}/transitions/dry-run",
                           json=body, headers=self.h(actor))

    def walk(self, task_id, events, actor=OWNER):
        last = None
        for ev in events:
            last = self.transition(task_id, ev, actor).json()
        return last

    def patch_task_payload(self, task_id, **fields):
        import json
        row = self.db.one("SELECT payload_json FROM ai_tasks WHERE id=?",
                          task_id)
        p = json.loads(row["payload_json"])
        p.update(fields)
        self.db.conn.execute("UPDATE ai_tasks SET payload_json=? WHERE id=?",
                             (json.dumps(p), task_id))
        self.db.conn.commit()

    # -- CORE-A6 artifact helpers --------------------------------------------
    def make_artifact(self, artifact_type="CASE_SUMMARY_DRAFT",
                      content_body="a normal case summary", requester=MANAGER,
                      **body):
        body.update(artifact_type=artifact_type, content_body=content_body)
        return self.c.post("/ai-artifacts", json=body,
                           headers=self.h(requester))

    def art(self, artifact_id, path="", actor=OWNER, method="GET", **body):
        url = f"/ai-artifacts/{artifact_id}{path}"
        if method == "GET":
            return self.c.get(url, headers=self.h(actor))
        return self.c.post(url, json=body, headers=self.h(actor))

    def latest_version_json(self, artifact_id, actor=OWNER):
        vs = self.c.get(f"/ai-artifacts/{artifact_id}/versions",
                        headers=self.h(actor)).json()["versions"]
        return vs[-1]

    def tamper_version(self, artifact_id, version_number, **envelope_fields):
        import json
        row = self.db.one(
            "SELECT id, payload_json FROM ai_artifact_versions WHERE "
            "artifact_id=? AND version_number=?", artifact_id, version_number)
        p = json.loads(row["payload_json"])
        for k, v in envelope_fields.items():
            if k == "content_body":
                p["content_envelope"]["content_body"] = v
            else:
                p[k] = v
        self.db.conn.execute(
            "UPDATE ai_artifact_versions SET payload_json=? WHERE id=?",
            (json.dumps(p), row["id"]))
        self.db.conn.commit()

    def approved_grant_task(self, task_type="merge_proposal"):
        """Create a task with a VALID approval grant (walked to APPROVAL_PENDING
        and approved by a second owner)."""
        hdr = self.h(MANAGER)
        cid = self.case_id(hdr)
        tk = self.c.post("/ai-tasks", json={
            "task_type": task_type, "task_title": "m",
            "task_description": "please do the thing", "subject_type": "case",
            "subject_id": cid}, headers=hdr).json()
        run = self.c.post("/ai-runs", json={"task_id": tk["task_id"]},
                          headers=hdr).json()
        ap = self.c.post("/ai-approvals", json={"run_id": run["run_id"]},
                         headers=hdr).json()
        acks = {a: True for a in ap["policy_decision_capsule"][
            "required_acknowledgements"]}
        self.c.post(f"/ai-approvals/{ap['approval_request_id']}/approve",
                    json={"viewed_package_hash": ap["approval_package_hash"],
                          "acknowledgements": acks, "challenge_passed": True},
                    headers=self.h(OWNER2))
        return tk["task_id"], ap["approval_request_id"]

    # -- TOOL-B1 tool registry helpers ----------------------------------------
    def clean_tool_body(self, **over):
        """A minimal admissible read-only tool descriptor body."""
        body = {"tool_name": "Search Cases", "category": "DATA_SEARCH",
                "side_effect_class": "PURE_READ",
                "tool_summary": "search local cases",
                "tool_description": "read only local case search",
                "reads_data_classes": ["INTERNAL"],
                "allowed_purposes": ["CASE_TRIAGE"],
                "declared_side_effects": ["PURE_READ"],
                "consent_requirement": "NONE",
                "prompt_context_exposure": "NAME_AND_SUMMARY"}
        body.update(over)
        return body

    def register_tool(self, body=None, requester=MANAGER, **over):
        b = body if body is not None else self.clean_tool_body(**over)
        return self.c.post("/ai-tools", json=b, headers=self.h(requester))

    def tool(self, tool_id, path="", actor=OWNER, method="GET", **body):
        url = f"/ai-tools/{tool_id}{path}"
        if method == "GET":
            return self.c.get(url, headers=self.h(actor))
        return self.c.post(url, json=body, headers=self.h(actor))

    def admit_tool(self, tool_id, actor=OWNER):
        return self.c.post(f"/ai-tools/{tool_id}/admit", headers=self.h(actor))

    def latest_tool_version(self, tool_id, actor=OWNER):
        vs = self.c.get(f"/ai-tools/{tool_id}/versions",
                        headers=self.h(actor)).json()["versions"]
        return vs[-1]

    def tamper_tool_version(self, tool_id, version_number, **fields):
        import json
        row = self.db.one(
            "SELECT id, payload_json FROM ai_tool_versions WHERE tool_id=? "
            "AND version_number=?", tool_id, version_number)
        p = json.loads(row["payload_json"])
        for k, v in fields.items():
            if k == "tool_description":
                p["descriptor"]["tool_description"] = v
            else:
                p[k] = v
        self.db.conn.execute(
            "UPDATE ai_tool_versions SET payload_json=? WHERE id=?",
            (json.dumps(p), row["id"]))
        self.db.conn.commit()

    def tamper_tool_head(self, tool_id, **cols):
        sets = ", ".join(f"{k}=?" for k in cols)
        self.db.conn.execute(f"UPDATE ai_tools SET {sets} WHERE id=?",
                             (*cols.values(), tool_id))
        self.db.conn.commit()

    # -- TOOL-B2 quality gate helpers -----------------------------------------
    def quality_tool_body(self, **over):
        """A clean, schema-complete descriptor that PASSES the quality gate."""
        body = {
            "tool_name": "Search Local Cases", "category": "DATA_SEARCH",
            "side_effect_class": "PURE_READ",
            "tool_summary": "read-only keyword search over local case records",
            "tool_description": "Read-only search over local case records by "
            "keyword; returns matching case ids and titles. No side effects, "
            "no external calls, no writes.",
            "reads_data_classes": ["INTERNAL"],
            "allowed_purposes": ["CASE_TRIAGE"],
            "declared_side_effects": ["PURE_READ"],
            "consent_requirement": "NONE",
            "prompt_context_exposure": "NAME_AND_SUMMARY",
            "input_schema": {"type": "object",
                             "properties": {"query": {"type": "string"}}},
            "output_schema": {"type": "object",
                              "properties": {"rows": {"type": "array"}}},
            "parameters": [{"name": "query", "type": "string", "required": True,
                            "description": "keyword to search local cases",
                            "data_class": "INTERNAL"}]}
        body.update(over)
        return body

    def register_quality_tool(self, body=None, requester=OWNER, **over):
        b = body if body is not None else self.quality_tool_body(**over)
        return self.c.post("/ai-tools", json=b, headers=self.h(requester))

    def quality_check(self, tool_id, actor=OWNER):
        return self.c.post(f"/ai-tools/{tool_id}/quality/check",
                           headers=self.h(actor))

    def q(self, tool_id, path="", actor=OWNER, method="GET", **body):
        url = f"/ai-tools/{tool_id}/quality{path}"
        if method == "GET":
            return self.c.get(url, headers=self.h(actor))
        return self.c.post(url, json=body, headers=self.h(actor))

    def checked_quality_tool(self, requester=OWNER, **over):
        """Register a clean schema-complete tool and run its quality check."""
        tid = self.register_quality_tool(requester=requester,
                                         **over).json()["tool_id"]
        rep = self.quality_check(tid, actor=requester).json()
        return tid, rep

    # -- TOOL-B3 contract helpers ---------------------------------------------
    def contract_tool(self, requester=OWNER, admit=True, **over):
        """Register a clean tool, run its quality check, and admit it so it is
        eligible for a PROJECTABLE_FOR_FUTURE contract."""
        tid = self.register_quality_tool(requester=requester,
                                         **over).json()["tool_id"]
        self.quality_check(tid, actor=requester)
        if admit:
            self.admit_tool(tid, actor=OWNER)
        return tid

    def create_contract(self, tool_id, actor=OWNER, **body):
        return self.c.post(f"/ai-tools/{tool_id}/contracts", json=body,
                           headers=self.h(actor))

    def contracted_tool(self, requester=OWNER, admit=True, **over):
        """Register+check+admit a tool and create its contract. Returns
        (tool_id, contract_dict)."""
        tid = self.contract_tool(requester=requester, admit=admit, **over)
        c = self.create_contract(tid, actor=requester).json()
        return tid, c

    def ct(self, tool_id, contract_id, path="", actor=OWNER, method="GET",
           **body):
        url = f"/ai-tools/{tool_id}/contracts/{contract_id}{path}"
        if method == "GET":
            return self.c.get(url, headers=self.h(actor))
        return self.c.post(url, json=body, headers=self.h(actor))

    def project(self, tool_id, contract_id, target="MCP_LIKE_TOOL_DESCRIPTOR",
                actor=OWNER, **body):
        body["target"] = target
        return self.c.post(
            f"/ai-tools/{tool_id}/contracts/{contract_id}/project", json=body,
            headers=self.h(actor))

    # -- TOOL-B4 pre-action reference monitor helpers -------------------------
    def preaction_tool(self, requester=OWNER, admit=True, **over):
        """Register+check+admit a tool and create its contract. Returns
        (tool_id, contract_dict) ready for action proposals."""
        return self.contracted_tool(requester=requester, admit=admit, **over)

    def clean_proposal_body(self, tool_id, contract, **over):
        """A minimal proposal that ALLOWS (for a future broker) against a clean
        pure-read tool: correct intent, in-scope, fresh state witness."""
        body = {"tool_id": tool_id, "contract_id": contract["contract_id"],
                "action_path": "search", "intent": "CASE_TRIAGE",
                "payload": {"query": "hi"},
                "requested_scope": {"category": "DATA_SEARCH"},
                "state_witness": {"epoch": contract["source_freshness_epoch"]},
                "idempotency_key": "idem-1", "logical_clock": 1}
        body.update(over)
        return body

    def propose(self, tool_id=None, contract=None, actor=OWNER, body=None,
                **over):
        """Submit an action proposal and return the raw Response."""
        if body is None:
            body = self.clean_proposal_body(tool_id, contract, **over)
        return self.c.post("/ai-tools/actions/proposals", json=body,
                           headers=self.h(actor))

    def decide(self, tool_id, contract, actor=OWNER, **over):
        """Submit a clean-ish proposal (with overrides) and return the decision
        dict."""
        return self.propose(tool_id, contract, actor=actor, **over).json()

    def pa(self, proposal_id, path="", actor=OWNER, method="GET", **body):
        url = f"/ai-tools/actions/proposals/{proposal_id}{path}"
        if method == "GET":
            return self.c.get(url, headers=self.h(actor))
        return self.c.post(url, json=body, headers=self.h(actor))

    def open_breaker(self, tool_id, actor=OWNER, state="OPEN", reason="test"):
        return self.c.post("/ai-tools/actions/circuit-breakers", json={
            "tool_id": tool_id, "breaker_state": state, "reason": reason},
            headers=self.h(actor))

    # -- TOOL-B5 null broker helpers ------------------------------------------
    def b4_decision(self, requester=OWNER, **over):
        """Register+check+admit a tool, create its contract, submit a clean B4
        proposal, and return (tool_id, contract, decision_dict)."""
        tid, contract = self.preaction_tool(requester=requester, **over)
        body = self.clean_proposal_body(tid, contract)
        d = self.c.post("/ai-tools/actions/proposals", json=body,
                        headers=self.h(requester)).json()
        return tid, contract, d

    def broker_request(self, b4_decision_id=None, actor=OWNER, body=None,
                       **over):
        """Create a null broker request from a B4 decision. Returns Response."""
        if body is None:
            body = {"b4_decision_id": b4_decision_id}
            body.update(over)
        return self.c.post("/ai-tools/broker/requests", json=body,
                           headers=self.h(actor))

    def prepared_broker(self, requester=OWNER, **over):
        """Full pipeline: admitted tool -> B4 ALLOWED decision -> null broker
        outcome. Returns (broker_request_id, outcome_dict)."""
        _, _, d = self.b4_decision(requester=requester, **over)
        o = self.broker_request(d["decision_id"], actor=requester).json()
        return o["broker_request_id"], o

    def br(self, broker_request_id, path="", actor=OWNER, method="GET", **body):
        url = f"/ai-tools/broker/requests/{broker_request_id}{path}"
        if method == "GET":
            return self.c.get(url, headers=self.h(actor))
        return self.c.post(url, json=body, headers=self.h(actor))

    # -- TOOL-B6 read-path runtime helpers ------------------------------------
    def b5_broker_request(self, requester=OWNER, **over):
        """Full pipeline to a clean B5 broker outcome. Returns (b5_broker_
        request_id, b5_outcome_dict)."""
        _, _, d = self.b4_decision(requester=requester, **over)
        o = self.broker_request(d["decision_id"], actor=requester).json()
        return o["broker_request_id"], o

    def runtime_snapshot(self, actor=OWNER, epoch="1", scope="case",
                         fields=None):
        """Freeze a local snapshot. Default fields: 2 PUBLIC + 1 CUSTOMER_
        SENSITIVE (which must never leak)."""
        if fields is None:
            fields = {"case_id": {"value": "C-1", "data_class": "PUBLIC"},
                      "status": {"value": "open", "data_class": "PUBLIC"},
                      "ssn": {"value": "999-99-9999",
                              "data_class": "CUSTOMER_SENSITIVE"}}
        return self.c.post("/ai-tools/runtime/snapshots", json={
            "epoch": epoch, "scope": scope, "fields": fields},
            headers=self.h(actor)).json()

    def runtime_request(self, b5_broker_request_id, snapshot_id, actor=OWNER,
                        body=None, **over):
        """Create a read-only runtime request. Defaults to a clean field-
        projection over the two PUBLIC fields. Returns Response."""
        if body is None:
            body = {"b5_broker_request_id": b5_broker_request_id,
                    "snapshot_id": snapshot_id, "adapter_kind":
                    "field_projection",
                    "allowed_sources": ["case_id", "status"],
                    "allowed_projection": ["case_id", "status"],
                    "requested_sources": ["case_id", "status"],
                    "requested_projection": ["case_id", "status"],
                    "requested_epoch": "1"}
            body.update(over)
        return self.c.post("/ai-tools/runtime/requests", json=body,
                           headers=self.h(actor))

    def prepared_runtime(self, requester=OWNER, snapshot_fields=None, **over):
        """Full pipeline: B4 -> B5 -> frozen snapshot -> read-only runtime
        outcome. Returns (runtime_request_id, outcome_dict)."""
        b5rid, _ = self.b5_broker_request(requester=requester)
        snap = self.runtime_snapshot(actor=requester, fields=snapshot_fields)
        o = self.runtime_request(b5rid, snap["snapshot_id"], actor=requester,
                                 **over).json()
        return o["runtime_request_id"], o

    def rt(self, runtime_request_id, path="", actor=OWNER, method="GET",
           **body):
        url = f"/ai-tools/runtime/requests/{runtime_request_id}{path}"
        if method == "GET":
            return self.c.get(url, headers=self.h(actor))
        return self.c.post(url, json=body, headers=self.h(actor))

    # -- TOOL-B7 transaction-escrow write-intent draft helpers ----------------
    def b6_runtime_outcome(self, requester=OWNER, **over):
        """Full pipeline to a clean B6 read-only runtime outcome. Returns
        (b6_runtime_request_id, b6_outcome_dict)."""
        return self.prepared_runtime(requester=requester, **over)

    def clean_write_intent_body(self, b6_runtime_request_id, **over):
        """A minimal admissible draft-only write-intent body. Default: a single
        INTERNAL status delta over a case, LOW risk, 1 SOURCE_STATE_HASH
        witness. Approvals are added separately (2-phase, see
        prepared_write_intent) because meaningful judgment binds the review
        package hash."""
        body = {
            "b6_runtime_request_id": b6_runtime_request_id,
            "target_entity": {"entity_type": "case", "entity_id": "E-1"},
            "proposed_deltas": [{"field_path": "status", "from_value": "open",
                                "to_value": "closed", "data_class": "INTERNAL"}],
            "intent": "update case status", "risk_tier": "LOW",
            "state_witnesses": [{"witness_class": "SOURCE_STATE_HASH",
                                "witness_hash": "sw-h", "epoch": 1}],
        }
        body.update(over)
        return body

    def write_intent(self, b6_runtime_request_id, actor=OWNER, body=None,
                     **over):
        """Create a write-intent draft. Returns the raw Response."""
        if body is None:
            body = self.clean_write_intent_body(b6_runtime_request_id, **over)
        return self.c.post("/ai-tools/write-intents", json=body,
                           headers=self.h(actor))

    def prepared_write_intent(self, requester=OWNER, approve=True, **over):
        """Full pipeline: B4 -> B5 -> B6 read-only runtime -> draft-only escrowed
        write-intent outcome. When approve=True, performs the 2-phase flow so the
        clean path reaches TRANSACTION_ESCROW_DRAFT_CREATED: prepare once to read
        the review-package hash, then re-create with an independent, server-
        verified approval that viewed exactly that package. Returns
        (write_intent_id, outcome_dict)."""
        b6rid, _ = self.b6_runtime_outcome(requester=requester)
        if not approve:
            o = self.write_intent(b6rid, actor=requester, **over).json()
            return o["write_intent_id"], o
        # Phase 1: read the content-addressed review digest (stable across the
        # per-request write_intent_id, so the approval below binds it).
        probe = self.write_intent(b6rid, actor=requester, **over).json()
        pkg = probe["review_package"]["review_content_digest"]
        appr = [{"approver_id": "reviewer2", "approver_role": "owner",
                 "server_verified": True, "challenge_passed": True,
                 "viewed_package_hash": pkg,
                 "acknowledgements": {"ACK_DRAFT_ONLY_NO_EXECUTION": True,
                                      "ACK_FUTURE_COMMIT_SEPARATE": True,
                                      "ACK_ESCROW_NON_EXECUTING": True,
                                      "ACK_REVIEWED_SHADOW_DELTAS": True}}]
        over2 = dict(over)
        over2["approvals"] = over.get("approvals", appr)
        o = self.write_intent(b6rid, actor=requester, **over2).json()
        return o["write_intent_id"], o

    def wi(self, write_intent_id, path="", actor=OWNER, method="GET", **body):
        url = f"/ai-tools/write-intents/{write_intent_id}{path}"
        if method == "GET":
            return self.c.get(url, headers=self.h(actor))
        return self.c.post(url, json=body, headers=self.h(actor))

    # -- TOOL-B8 machine-checkable pre-B9 assurance / commit-sim helpers -------
    def b7_write_intent_outcome(self, requester=OWNER, **over):
        """Full pipeline to a clean B7 TRANSACTION_ESCROW_DRAFT_CREATED outcome.
        Returns (write_intent_id, b7_outcome_dict)."""
        return self.prepared_write_intent(requester=requester, **over)

    def commit_simulation(self, b7_write_intent_id, actor=OWNER, body=None,
                          **over):
        """Create a commit simulation from a B7 write-intent. Returns the raw
        Response."""
        if body is None:
            body = {"b7_write_intent_id": b7_write_intent_id}
            body.update(over)
        return self.c.post("/ai-tools/commit-simulations", json=body,
                           headers=self.h(actor))

    def prepared_commit_simulation(self, requester=OWNER, **over):
        """Full pipeline: B4 -> B5 -> B6 -> B7 escrow draft -> simulation-only
        pre-B9 assurance outcome. Returns (commit_simulation_id, outcome_dict).
        With clean defaults the outcome is B8_V5_ACCEPTED (pre-B9 evidence
        only; B9 revalidation still required; no real commit)."""
        wid, _ = self.b7_write_intent_outcome(requester=requester)
        o = self.commit_simulation(wid, actor=requester, **over).json()
        return o["commit_simulation_id"], o

    def cs(self, commit_simulation_id, path="", actor=OWNER, method="GET",
           **body):
        url = f"/ai-tools/commit-simulations/{commit_simulation_id}{path}"
        if method == "GET":
            return self.c.get(url, headers=self.h(actor))
        return self.c.post(url, json=body, headers=self.h(actor))

    # -- TOOL-B9 Finalis Transaction Twin / local-transaction helpers ---------
    def b8_accepted_outcome(self, requester=OWNER, **over):
        """Full pipeline to a clean B8 B8_V5_ACCEPTED outcome. Returns
        (commit_simulation_id, b8_outcome_dict)."""
        return self.prepared_commit_simulation(requester=requester, **over)

    def clean_local_tx_body(self, b8_commit_simulation_id, **over):
        """A minimal admissible B9 local-transaction body: a single local
        'status' delta on a case object, authority from server RBAC, a server-
        verified approval, WEB_PORTAL surface."""
        body = {
            "b8_commit_simulation_id": b8_commit_simulation_id,
            "object_reference": "case:E-1", "requested_intent":
            "mark local status reviewed", "source_surface": "WEB_PORTAL",
            "planned_delta": {"status": "reviewed"},
            "current_local_state": {"status": "new"},
            "allowed_local_scope": ["status"],
            "authority_basis": {"source": "SERVER_RBAC"},
            "approval_record": {"server_verified": True, "refs": ["ap-1"]},
            "evidence_refs": ["ev-1"], "policy_refs": ["pol-1"],
            "idempotency_key": "idem-1",
        }
        body.update(over)
        return body

    def local_tx(self, b8_commit_simulation_id, op="prepare", actor=OWNER,
                 body=None, **over):
        """Prepare/validate/commit-local a B9 transaction. `op` in
        prepare|validate|commit-local. Returns the raw Response."""
        if body is None:
            body = self.clean_local_tx_body(b8_commit_simulation_id, **over)
        return self.c.post(f"/ai-tools/local-transactions/{op}", json=body,
                           headers=self.h(actor))

    def prepared_local_tx(self, requester=OWNER, op="commit-local", **over):
        """Full pipeline: B4..B8 -> B8_V5_ACCEPTED -> B9 local transaction.
        With clean defaults the outcome is B9_LOCAL_COMMIT_APPLIED (a local,
        reversible internal commit; no external effect). Returns
        (transaction_id, outcome_dict)."""
        b8id, _ = self.b8_accepted_outcome(requester=requester)
        o = self.local_tx(b8id, op=op, actor=requester, **over).json()
        return o["transaction_id"], o

    def lt(self, transaction_id, path="", actor=OWNER, method="GET", **body):
        url = f"/ai-tools/local-transactions/{transaction_id}{path}"
        if method == "GET":
            return self.c.get(url, headers=self.h(actor))
        return self.c.post(url, json=body, headers=self.h(actor))

    # -- TOOL-B9.1 Recovery / Chaos Sentinel / Proof-of-Recovery helpers ------
    def committed_local_tx(self, requester=OWNER, **over):
        """A B9 transaction committed to local reversible state
        (B9_LOCAL_COMMIT_APPLIED). Returns (transaction_id, b9_outcome)."""
        return self.prepared_local_tx(requester=requester, op="commit-local",
                                      **over)

    def recover(self, transaction_id, action="run", actor=OWNER, body=None,
                **over):
        """Run a B9.1 recovery action over a B9 transaction. `action` in
        status|plan|run|rollback-local|abort|quarantine|stuck|crash-drill.
        Returns the raw Response; `.json()` is the recovery outcome. Any kernel
        override (kill_switch=, recovery_authority_basis=, poe_tamper=, ...) is
        passed straight through."""
        payload = {"transaction_id": transaction_id}
        if body:
            payload.update(body)
        payload.update(over)
        return self.c.post(
            f"/ai-tools/local-transactions/recovery/{action}", json=payload,
            headers=self.h(actor))

    def prepared_recovery(self, requester=OWNER, action="run", **over):
        """Full pipeline: B4..B8 -> B9 committed local tx -> B9.1 recovery.
        With clean defaults over a committed transaction the recovery evaluation
        is clean (no external effect, inert outbox preserved, safety
        monotonicity + double-entry reconciliation hold). Returns
        (recovery_id, outcome)."""
        txid, _ = self.committed_local_tx(requester=requester)
        o = self.recover(txid, action=action, actor=requester, **over).json()
        return o["recovery_id"], o

    def rc(self, recovery_id, slug, actor=OWNER):
        """GET a recovery sub-object / view endpoint by recovery_id."""
        return self.c.get(
            f"/ai-tools/local-transactions/recovery/{slug}"
            f"?recovery_id={recovery_id}", headers=self.h(actor))

    # -- TOOL-B9.2 Governed Work Lineage Observatory helpers ------------------
    def clean_work_body(self, b9_transaction_id=None, b91_recovery_id=None,
                        **over):
        """A minimal clean Governed Work Run body: a valid principal + one
        report artifact with a source + local delivery intent. With a committed
        B9 transaction bound, the observation certifies (WORK_OUTCOME_CERTIFIED /
        PROVEN)."""
        body = {"source_principal_id": "user:1",
                "effective_principal_id": "user:1",
                "artifacts": [{"id": "a1", "type": "REPORT",
                               "sources": ["s1"], "content": "x"}],
                "delivery_status": "LOCAL_INTENT_ONLY"}
        if b9_transaction_id:
            body["b9_transaction_id"] = b9_transaction_id
        if b91_recovery_id:
            body["b91_recovery_id"] = b91_recovery_id
        body.update(over)
        return body

    def observe_work(self, action="observe-work-run", actor=OWNER, body=None,
                     **over):
        """POST a B9.2 derived observation action. `action` in
        observe-work-run|verify-work-run|rebuild-local-observation|
        run-local-canary|work-observability-drill. Returns the raw Response."""
        payload = self.clean_work_body(**over) if body is None else body
        return self.c.post(
            f"/ai-tools/local-transactions/observability/{action}",
            json=payload, headers=self.h(actor))

    def observed_work(self, requester=OWNER, bind_transaction=True,
                      bind_recovery=False, **over):
        """Full pipeline: B4..B8 -> B9 committed local tx (-> B9.1 recovery) ->
        B9.2 observation. Returns (work_run_id, outcome). With a bound committed
        transaction and clean defaults the outcome is WORK_OUTCOME_CERTIFIED."""
        b9id = b91id = None
        if bind_transaction or bind_recovery:
            b9id, _ = self.committed_local_tx(requester=requester)
        if bind_recovery:
            b91id = self.recover(b9id, action="run", actor=requester).json()[
                "recovery_id"]
        body = self.clean_work_body(b9_transaction_id=b9id, b91_recovery_id=b91id,
                                    **over)
        o = self.observe_work(actor=requester, body=body).json()
        return o["work_run_id"], o

    def wo(self, work_run_id, slug, actor=OWNER):
        """GET a B9.2 work-lineage sub-object / view endpoint by work_run_id."""
        return self.c.get(
            f"/ai-tools/local-transactions/observability/{slug}/{work_run_id}",
            headers=self.h(actor))

    # -- EMP-A1 Employee Work Inbox helpers -----------------------------------
    def clean_work_intake(self, **over):
        """A minimal admissible work-intake body: a portal-manual case_summary
        over a case target with a fresh idempotency key. Clean defaults admit
        to READY (ADMIT_READY)."""
        import uuid as _uuid
        body = {
            "source_type": "PORTAL_MANUAL", "source_schema_version": "1",
            "work_type": "case_summary", "requested_target_refs": ["case:E-1"],
            "canonical_parameters": {"target": "case:E-1"},
            "idempotency_key": "idem-" + _uuid.uuid4().hex[:12],
            "raw_payload": {"note": "summarize this case"},
        }
        body.update(over)
        return body

    def submit_work(self, actor=OWNER, body=None, **over):
        """POST a work-intake request. Returns the raw Response; `.json()` is the
        admission outcome ({work_item, disposition, decision_hash, ...})."""
        payload = self.clean_work_intake(**over) if body is None else body
        return self.c.post("/ai-employee/work-inbox/items", json=payload,
                           headers=self.h(actor))

    def admitted_work(self, actor=OWNER, **over):
        """Submit a clean work item. Returns (work_item_id, outcome). With clean
        defaults the item is admitted READY (ADMIT_READY)."""
        o = self.submit_work(actor=actor, **over).json()
        wi = o.get("work_item") or {}
        return wi.get("work_item_id"), o

    def wki(self, work_item_id, path="", actor=OWNER, method="GET", **body):
        """GET/POST an EMP-A1 work-item endpoint."""
        url = f"/ai-employee/work-inbox/items/{work_item_id}{path}"
        if method == "GET":
            return self.c.get(url, headers=self.h(actor))
        return self.c.post(url, json=body or {}, headers=self.h(actor))

    def ready_to_handoff(self, actor=OWNER, **over):
        """Full pipeline: admit -> claim -> prepare-handoff. Returns
        (work_item_id, handoff_response). Prepares exactly one fenced single-use
        EMP-A2 handoff capability; creates NO run."""
        wid, _ = self.admitted_work(actor=actor, **over)
        self.wki(wid, "/claim", actor=actor, method="POST")
        r = self.wki(wid, "/prepare-handoff", actor=actor, method="POST")
        return wid, r


@pytest.fixture()
def gate():
    return Gate()
