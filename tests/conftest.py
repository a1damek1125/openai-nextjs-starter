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


@pytest.fixture()
def gate():
    return Gate()
