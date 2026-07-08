"""Finalis Portal API — FastAPI over the tested domain core.

UI → these endpoints → domain services (unchanged, 212-test core) →
PortalStore persistence → DbAuditLog (chain in SQL). Providers are the
existing mocks behind real interfaces (env-configurable later).
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..actions.engine import ActionCommunicationEngine
from ..actions.models import ActionRequest, ChannelPreference
from ..case_services import (ActionGateService, CompletionLoopService,
                             MissingInfoService)
from ..dashboard import DashboardService, PermissionDenied
from ..dashboard_html import render_dashboard
from ..models import Case
from ..state_machine import CaseState, IllegalTransition, transition
from ..voice.conversation_intelligence import (ConversationIntelligence,
                                               DiarizedSegment)
from .auth import AuthService, verify_token
from .db import Database, DbAuditLog, utcnow
from .store import PortalStore
from . import ui


def create_app(db_path: str = ":memory:") -> FastAPI:
    app = FastAPI(title="Finalis AI Portal", version="0.1.0")
    db = Database(db_path)
    store = PortalStore(db)
    audit = DbAuditLog(db)
    auth = AuthService(db)
    ace = ActionCommunicationEngine(audit)
    loop = CompletionLoopService(audit)
    app.state.db, app.state.store, app.state.audit = db, store, audit
    app.state.auth, app.state.ace, app.state.loop = auth, ace, loop

    # ---- auth dependency -------------------------------------------------------
    def current_user(authorization: str = Header(default="")) -> dict:
        token = authorization.removeprefix("Bearer ").strip()
        body = verify_token(token) if token else None
        if body is None:
            raise HTTPException(401, "not authenticated")
        return body

    def require_role(user: dict, *roles: str) -> None:
        if user["role"] not in roles:
            raise HTTPException(403, f"role {user['role']} not permitted")

    def load_case_or_404(case_id: str, user: dict) -> Case:
        case = store.load_case(case_id, tenant_id=user["tid"])
        if case is None:
            raise HTTPException(404, "case not found")   # incl. cross-tenant
        return case

    def dash_service(tenant_id: str) -> DashboardService:
        """Rebuild the dashboard projection from persisted cases."""
        svc = DashboardService(audit)
        for meta in store.list_cases(tenant_id=tenant_id):
            case = store.load_case(meta["id"], tenant_id=tenant_id)
            svc.register_case(
                case, title=meta["title"],
                client_name=meta["client_name"] or "?",
                offer_sent_at=datetime.fromisoformat(meta["offer_sent_at"])
                if meta["offer_sent_at"] else None)
        for d in db.all("SELECT * FROM message_drafts WHERE tenant_id=? "
                        "AND approval_status='PENDING'", tenant_id):
            svc.register_approval(
                tenant_id=tenant_id, case_id=d["case_id"],
                action_type="message_draft", draft_message=d["text"],
                reason=d["risk_level"] + " risk draft",
                risk_level=d["risk_level"],
                created_at=datetime.fromisoformat(d["created_at"]))
        return svc

    # ---- auth ------------------------------------------------------------------
    @app.post("/auth/login")
    async def login(body: dict):
        result = auth.login(body.get("email", ""), body.get("password", ""))
        if result is None:
            raise HTTPException(401, "invalid credentials")
        return result

    @app.get("/auth/me")
    async def me(user: dict = Depends(current_user)):
        return {"user_id": user["uid"], "tenant_id": user["tid"],
                "role": user["role"]}

    @app.post("/auth/logout")
    async def logout(user: dict = Depends(current_user)):
        return {"ok": True}   # stateless tokens: client discards

    # ---- dashboard ---------------------------------------------------------------
    @app.get("/dashboard/summary")
    async def dashboard_summary(user: dict = Depends(current_user)):
        s = dash_service(user["tid"]).summary(user["tid"],
                                              now=datetime.utcnow())
        return s.__dict__

    @app.get("/dashboard/{section}")
    async def dashboard_section(section: str,
                                user: dict = Depends(current_user)):
        svc = dash_service(user["tid"])
        now = datetime.utcnow()
        tid = user["tid"]
        handlers = {
            "action-queue": lambda: [i.__dict__ for i in
                                     svc.action_queue(tid, now=now)],
            "approval-queue": lambda: [i.__dict__ for i in
                                       svc.approval_queue(tid)],
            "stuck-cases": lambda: svc.stuck_cases(tid, now=now),
            "missing-info": lambda: svc.missing_info(tid),
            "promises": lambda: svc.promises(tid, now=now),
            "offers-follow-up": lambda: svc.offers_followup(tid, now=now),
            "pipeline": lambda: svc.pipeline(tid),
            "risk-alerts": lambda: svc.risk_alerts(tid, now=now),
            "activity": lambda: [e.__dict__ for e in svc.activity(tid)],
        }
        if section not in handlers:
            raise HTTPException(404, "unknown section")
        return JSONResponse(json.loads(json.dumps(handlers[section](),
                                                  default=str)))

    # ---- cases ---------------------------------------------------------------------
    @app.get("/cases")
    async def list_cases(state: Optional[str] = None,
                         user: dict = Depends(current_user)):
        return store.list_cases(tenant_id=user["tid"], state=state)

    @app.post("/cases")
    async def create_case(body: dict, user: dict = Depends(current_user)):
        require_role(user, "owner", "manager", "operator")
        tid = user["tid"]
        party_id = str(uuid.uuid4())
        store.create_party(tenant_id=tid, party_id=party_id, type_="client",
                           name=body.get("client_name", "Unknown"),
                           phone=body.get("phone", ""),
                           address=body.get("address", ""))
        case = Case(tenant_id=tid, autonomy_level=3)
        case.value_estimate = float(body.get("value_estimate", 0))
        case.lead_score = float(body.get("lead_score", 50))
        case.next_best_action = {"type": "start_intake"}
        case.next_action_due_at = datetime.utcnow()
        case.last_progress_at = datetime.utcnow()
        store.save_case(case, title=body.get("title", "New case"),
                        client_party_id=party_id)
        audit.append(event_type="CASE_CREATED", actor=user["uid"],
                     case_id=case.id, payload={"via": "api"})
        return {"case_id": case.id, "state": case.state.value}

    @app.get("/cases/{case_id}")
    async def get_case(case_id: str, user: dict = Depends(current_user)):
        meta = store.case_meta(case_id, tenant_id=user["tid"])
        if meta is None:
            raise HTTPException(404, "case not found")
        case = load_case_or_404(case_id, user)
        meta["missing_items"] = [m.__dict__ for m in case.missing_items]
        meta["promises"] = [
            {**p.__dict__, "due_at": p.due_at.isoformat()}
            for p in case.promises]
        meta["documents"] = [dict(r) for r in db.all(
            "SELECT * FROM documents WHERE case_id=? AND tenant_id=?",
            case_id, user["tid"])]
        meta["offers"] = [dict(r) for r in db.all(
            "SELECT * FROM offers WHERE case_id=? AND tenant_id=?",
            case_id, user["tid"])]
        meta["drafts"] = [dict(r) for r in db.all(
            "SELECT * FROM message_drafts WHERE case_id=? AND tenant_id=?",
            case_id, user["tid"])]
        return json.loads(json.dumps(meta, default=str))

    @app.post("/cases/{case_id}/transition")
    async def transition_case(case_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_role(user, "owner", "manager", "operator")
        case = load_case_or_404(case_id, user)
        try:
            transition(case, CaseState(body["to_state"]),
                       actor=user["uid"], reason=body.get("reason", "api"),
                       audit_log=audit,
                       human_override=bool(body.get("human_override")),
                       scheduled_wake=bool(body.get("scheduled_wake")))
        except IllegalTransition as e:
            raise HTTPException(409, f"illegal transition: {e}")
        if case.next_best_action is None and case.is_active():
            case.next_best_action = {"type": "review_case"}
            case.next_action_due_at = datetime.utcnow()
        if body.get("offer_sent"):
            db.update("cases", case.id, {"offer_sent_at": utcnow()})
        store.save_case(case)
        return {"state": case.state.value}

    @app.get("/cases/{case_id}/timeline")
    @app.get("/cases/{case_id}/audit-events")
    async def case_timeline(case_id: str,
                            user: dict = Depends(current_user)):
        load_case_or_404(case_id, user)
        rows = db.all("SELECT * FROM audit_events WHERE case_id=? "
                      "ORDER BY seq", case_id)
        return [{"id": r["id"], "event_type": r["event_type"],
                 "actor": r["actor"], "created_at": r["created_at"],
                 "payload": json.loads(r["payload_json"])} for r in rows]

    # ---- conversation ----------------------------------------------------------------
    @app.post("/cases/{case_id}/transcripts")
    async def add_transcript(case_id: str, body: dict,
                             user: dict = Depends(current_user)):
        load_case_or_404(case_id, user)
        tr_id = str(uuid.uuid4())
        db.insert("transcripts", {"id": tr_id, "tenant_id": user["tid"],
                                  "case_id": case_id,
                                  "segments_json": json.dumps(
                                      body["segments"])})
        return {"transcript_id": tr_id}

    @app.post("/cases/{case_id}/analyze-conversation")
    async def analyze(case_id: str, user: dict = Depends(current_user)):
        case = load_case_or_404(case_id, user)
        row = db.one("SELECT * FROM transcripts WHERE case_id=? "
                     "ORDER BY created_at DESC", case_id)
        if row is None:
            raise HTTPException(404, "no transcript")
        segments = [DiarizedSegment(**s)
                    for s in json.loads(row["segments_json"])]
        ci = ConversationIntelligence(audit, tenant_id=user["tid"])
        analysis = ci.analyze(row["id"], segments, case_id=case_id)
        # Apply the case-update payload to the persisted aggregate.
        from ..models import Promise as P, MissingItem as MI
        for m in analysis.missing_items:
            if m["type"] not in {x.field_key for x in case.missing_items}:
                case.missing_items.append(MI(
                    field_key=m["type"], label=m["type"],
                    weight=0.9 if m["severity"] == "high" else 0.5,
                    blocks_quote=(m["blocks"] == "quote_preparation")))
        for p in analysis.promises:
            case.promises.append(P(
                promisor=p["who"], what=p["what"],
                due_at=datetime.utcnow() + timedelta(hours=24),
                importance=.7, dependency_impact=.8))
        case.next_best_action = analysis.next_action
        case.next_action_due_at = datetime.utcnow() + timedelta(hours=4)
        case.last_progress_at = datetime.utcnow()
        store.save_case(case)
        db.update("transcripts", row["id"], {
            "analysis_json": json.dumps(analysis.case_update_payload,
                                        default=str)})
        return json.loads(json.dumps(analysis.case_update_payload,
                                     default=str))

    # ---- completion loop ----------------------------------------------------------------
    @app.post("/completion-loop/run-case/{case_id}")
    async def run_case(case_id: str, user: dict = Depends(current_user)):
        case = load_case_or_404(case_id, user)
        result = loop.run_case(case, now=datetime.utcnow())
        store.save_case(case)
        return json.loads(json.dumps(result, default=str))

    @app.post("/completion-loop/run")
    async def run_all(user: dict = Depends(current_user)):
        results = []
        for meta in store.list_cases(tenant_id=user["tid"]):
            case = store.load_case(meta["id"], tenant_id=user["tid"])
            results.append(loop.run_case(case, now=datetime.utcnow()))
            store.save_case(case)
        return json.loads(json.dumps(results, default=str))

    # ---- actions ----------------------------------------------------------------------------
    @app.post("/actions/request")
    async def request_action(body: dict,
                             user: dict = Depends(current_user)):
        case = load_case_or_404(body["case_id"], user)
        req = ActionRequest(tenant_id=user["tid"], case_id=case.id,
                            action_type=body["action_type"],
                            reason=body.get("reason", "api"),
                            risk_level=body.get("risk_level", "low"),
                            payload=body.get("payload", {}))
        meta = store.case_meta(case.id, tenant_id=user["tid"])
        req.payload.setdefault("recipient",
                               meta.get("client_phone") or "unknown")
        prefs = ChannelPreference(tenant_id=user["tid"], party_id="client")
        outcome = ace.handle(case, req, prefs=prefs, consents=[],
                             now=datetime.utcnow())
        db.insert("action_requests", {
            "id": req.id, "tenant_id": user["tid"], "case_id": case.id,
            "action_type": req.action_type, "reason": req.reason,
            "source": "api", "risk_level": req.risk_level,
            "payload_json": json.dumps(req.payload, default=str),
            "status": outcome.status})
        if outcome.draft is not None:
            db.insert("message_drafts", {
                "id": outcome.draft.id, "tenant_id": user["tid"],
                "case_id": case.id, "action_request_id": req.id,
                "language": outcome.draft.language,
                "channel": outcome.draft.channel,
                "text": outcome.draft.text,
                "risk_level": outcome.draft.risk_level,
                "approval_status": outcome.draft.approval_status})
        if outcome.execution is not None:
            db.insert("executions", {
                "id": outcome.execution.id, "tenant_id": user["tid"],
                "case_id": case.id, "action_request_id": req.id,
                "channel": outcome.execution.channel,
                "provider": outcome.execution.provider,
                "status": outcome.execution.status,
                "executed_at": utcnow(),
                "result_json": json.dumps(outcome.execution.result,
                                          default=str)})
        if outcome.upload_url:
            link = list(ace.uploads.links.values())[-1]
            db.insert("upload_links", {
                "id": link.id, "tenant_id": user["tid"], "case_id": case.id,
                "token_hash": link.token_hash, "purpose": link.purpose,
                "expires_at": link.expires_at.isoformat(),
                "status": link.status})
        store.save_case(case)
        return {"status": outcome.status, "reason": outcome.reason,
                "draft_id": outcome.draft.id if outcome.draft else None,
                "upload_url": outcome.upload_url,
                "approval_id": outcome.approval_id}

    @app.post("/actions/{draft_id}/approve")
    @app.post("/actions/{draft_id}/reject")
    async def decide_action(draft_id: str, body: dict, request: Request,
                            user: dict = Depends(current_user)):
        require_role(user, "owner", "manager")
        decision = "approve" if request.url.path.endswith("approve") \
            else "reject"
        row = db.one("SELECT * FROM message_drafts WHERE id=? AND "
                     "tenant_id=?", draft_id, user["tid"])
        if row is None:
            raise HTTPException(404, "draft not found")
        outcome = ace.decide_approval(
            draft_id, approver=user["uid"], decision=decision,
            now=datetime.utcnow(),
            edited_text=body.get("edited_message"),
            reason=body.get("reason", ""))
        new_status = "APPROVED" if decision == "approve" else "REJECTED"
        fields = {"approval_status": new_status}
        if body.get("edited_message"):
            fields["edited_text"] = body["edited_message"]
        db.update("message_drafts", draft_id, fields)
        return {"approval_status": new_status,
                "executed": bool(outcome and outcome.status == "executed")}

    # ---- upload links --------------------------------------------------------------------------
    @app.post("/upload-links")
    async def create_upload_link(body: dict,
                                 user: dict = Depends(current_user)):
        case = load_case_or_404(body["case_id"], user)
        link, url = ace.uploads.create(
            tenant_id=user["tid"], case_id=case.id,
            purpose=body.get("purpose", "installation_photo"),
            now=datetime.utcnow())
        db.insert("upload_links", {
            "id": link.id, "tenant_id": user["tid"], "case_id": case.id,
            "token_hash": link.token_hash, "purpose": link.purpose,
            "expires_at": link.expires_at.isoformat(),
            "status": link.status})
        return {"upload_url": url, "link_id": link.id}

    @app.get("/upload-links/{token}")
    async def open_upload_link(token: str):
        link = ace.uploads.open(token, datetime.utcnow())
        if link is None:
            raise HTTPException(404, "link invalid or expired")
        db.update("upload_links", link.id, {"status": link.status})
        return {"purpose": link.purpose, "status": link.status}

    @app.post("/upload-links/{token}/upload")
    async def upload_via_link(token: str, body: dict):
        """Client-facing: no auth (token IS the credential)."""
        link = ace.uploads.open(token, datetime.utcnow())
        if link is None:
            raise HTTPException(404, "link invalid or expired")
        ok = ace.uploads.use(token, datetime.utcnow(),
                             mime=body.get("mime", "image/jpeg"),
                             size_mb=float(body.get("size_mb", 1.0)))
        if not ok:
            raise HTTPException(422, "file type or size not allowed")
        doc_id = str(uuid.uuid4())
        db.insert("documents", {
            "id": doc_id, "tenant_id": link.tenant_id,
            "case_id": link.case_id, "doc_type": link.purpose,
            "filename": body.get("filename", "upload.jpg"),
            "mime": body.get("mime", "image/jpeg"),
            "size_bytes": int(float(body.get("size_mb", 1.0)) * 1e6),
            "storage_path": f"local://uploads/{doc_id}"})
        db.update("upload_links", link.id,
                  {"status": "USED", "used_at": utcnow()})
        # Resolve the matching missing item on the persisted aggregate.
        case = store.load_case(link.case_id, tenant_id=link.tenant_id)
        if case is not None:
            MissingInfoService.resolve(case, link.purpose, audit=audit,
                                       source="upload")
            case.last_progress_at = datetime.utcnow()
            store.save_case(case)
        return {"document_id": doc_id, "resolved": link.purpose}

    # ---- documents / offers -----------------------------------------------------------------------
    @app.get("/cases/{case_id}/documents")
    async def case_documents(case_id: str,
                             user: dict = Depends(current_user)):
        load_case_or_404(case_id, user)
        return [dict(r) for r in db.all(
            "SELECT * FROM documents WHERE case_id=? AND tenant_id=?",
            case_id, user["tid"])]

    @app.post("/cases/{case_id}/offers")
    async def create_offer(case_id: str, body: dict,
                           user: dict = Depends(current_user)):
        require_role(user, "owner", "manager")
        load_case_or_404(case_id, user)
        offer_id = str(uuid.uuid4())
        db.insert("offers", {"id": offer_id, "tenant_id": user["tid"],
                             "case_id": case_id,
                             "price": float(body.get("price", 0)),
                             "scope": body.get("scope", "")})
        audit.append(event_type="OFFER_CREATED", actor=user["uid"],
                     case_id=case_id, payload={"offer_id": offer_id})
        return {"offer_id": offer_id}

    @app.post("/offers/{offer_id}/send")
    async def send_offer(offer_id: str, user: dict = Depends(current_user)):
        require_role(user, "owner", "manager")
        row = db.one("SELECT * FROM offers WHERE id=? AND tenant_id=?",
                     offer_id, user["tid"])
        if row is None:
            raise HTTPException(404, "offer not found")
        db.update("offers", offer_id, {"status": "sent",
                                       "sent_at": utcnow()})
        db.update("cases", row["case_id"], {"offer_sent_at": utcnow()})
        audit.append(event_type="OFFER_SENT_EVENT", actor=user["uid"],
                     case_id=row["case_id"], payload={"offer_id": offer_id,
                                                      "provider": "mock"})
        return {"status": "sent"}

    @app.post("/offers/{offer_id}/simulate-client-response")
    async def offer_response(offer_id: str, body: dict,
                             user: dict = Depends(current_user)):
        row = db.one("SELECT * FROM offers WHERE id=? AND tenant_id=?",
                     offer_id, user["tid"])
        if row is None:
            raise HTTPException(404, "offer not found")
        response = body.get("response", "accepted")
        db.update("offers", offer_id, {"client_response": response,
                                       "status": response})
        audit.append(event_type="CLIENT_REPLIED", actor="client",
                     case_id=row["case_id"], payload={"offer_id": offer_id,
                                                      "response": response})
        return {"client_response": response}

    # ---- lifecycle: mock invoice / payment / fulfillment ---------------------------
    from ..lifecycle.playbooks import HVAC_HOME_SERVICES
    from ..lifecycle.completion import CaseFacts, can_complete
    from ..lifecycle.vector import (DealState, FulfillmentState,
                                    LifecycleVector, TransactionState)

    def load_vector(case_id: str) -> LifecycleVector:
        row = db.one("SELECT lifecycle_json FROM cases WHERE id=?", case_id)
        if row and row["lifecycle_json"]:
            data = json.loads(row["lifecycle_json"])
            return LifecycleVector(
                deal=DealState(data["deal"]),
                transaction=TransactionState(data["transaction"]),
                fulfillment=FulfillmentState(data["fulfillment"]))
        return LifecycleVector()

    def save_vector(case_id: str, v: LifecycleVector) -> None:
        db.update("cases", case_id, {"lifecycle_json": json.dumps(
            {"deal": v.deal.value, "transaction": v.transaction.value,
             "fulfillment": v.fulfillment.value})})

    @app.get("/cases/{case_id}/lifecycle")
    async def get_lifecycle(case_id: str,
                            user: dict = Depends(current_user)):
        load_case_or_404(case_id, user)
        v = load_vector(case_id)
        facts = CaseFacts(vector=v, closure_evidence_id="portal",
                          completion_confirmed=True, contract_signed=True)
        check = can_complete(facts, HVAC_HOME_SERVICES)
        return {"deal": v.deal.value, "transaction": v.transaction.value,
                "fulfillment": v.fulfillment.value,
                "view": v.derived_outcome_view(),
                "message": v.business_language(),
                "can_complete": check.ok,
                "blocked_reasons": check.blocked_reasons,
                "next_best_action": check.next_best_action}

    @app.post("/cases/{case_id}/lifecycle/accept-offer")
    @app.post("/cases/{case_id}/lifecycle/invoice")
    @app.post("/cases/{case_id}/lifecycle/payment")
    @app.post("/cases/{case_id}/lifecycle/fulfillment-schedule")
    @app.post("/cases/{case_id}/lifecycle/fulfillment-complete")
    async def lifecycle_step(case_id: str, request: Request,
                             user: dict = Depends(current_user)):
        """MOCK invoice/payment/fulfillment providers (clearly mock —
        real billing/scheduling providers replace these endpoints' guts)."""
        require_role(user, "owner", "manager")
        load_case_or_404(case_id, user)
        v = load_vector(case_id)
        step = request.url.path.rsplit("/", 1)[1]
        if step == "accept-offer":
            v.deal = DealState.ACCEPTED_BY_CLIENT
            v.transaction = TransactionState.INVOICE_REQUIRED
            v.fulfillment = FulfillmentState.REQUIRED
            audit.append(event_type="CASE_WON_NOT_FULFILLED", actor="mock",
                         case_id=case_id, payload={"provider": "mock"})
        elif step == "invoice":
            v.transaction = TransactionState.INVOICE_ISSUED
            audit.append(event_type="INVOICE_ISSUED", actor="mock-invoice",
                         case_id=case_id, payload={"is_mock": True})
        elif step == "payment":
            v.transaction = TransactionState.PAID
            audit.append(event_type="PAYMENT_RECEIVED", actor="mock-payment",
                         case_id=case_id, payload={"is_mock": True})
        elif step == "fulfillment-schedule":
            v.fulfillment = FulfillmentState.SCHEDULED
            audit.append(event_type="FULFILLMENT_SCHEDULED",
                         actor="mock-fulfillment", case_id=case_id,
                         payload={"is_mock": True})
        elif step == "fulfillment-complete":
            v.fulfillment = FulfillmentState.COMPLETED
            audit.append(event_type="FULFILLMENT_COMPLETED",
                         actor="mock-fulfillment", case_id=case_id,
                         payload={"is_mock": True})
        save_vector(case_id, v)
        return {"view": v.derived_outcome_view(),
                "message": v.business_language()}

    # ---- telephony (mock provider) ----------------------------------------------------
    from ..telephony.engine import CallControlEngine
    from ..telephony.models import ContactCallState
    tele = CallControlEngine(audit)
    app.state.telephony = tele

    @app.post("/telephony/inbound/simulate")
    async def telephony_inbound(body: dict,
                                user: dict = Depends(current_user)):
        r = tele.simulate_inbound(
            tenant_id=user["tid"],
            caller_number=body.get("caller_number", "+48600000000"),
            segments=body.get("segments", []),
            recording_consent=body.get("recording_consent", "granted"),
            emergency=bool(body.get("emergency")),
            asks_for_human=bool(body.get("asks_for_human")))
        s = r.session
        # Persist the engine-created case into the portal DB.
        if s.case_id and store.case_meta(s.case_id,
                                         tenant_id=user["tid"]) is None:
            engine_case = tele.graph.cases.get(s.case_id)
            if engine_case is not None:
                party_id = str(uuid.uuid4())
                store.create_party(tenant_id=user["tid"],
                                   party_id=party_id, type_="client",
                                   name="Inbound caller",
                                   phone=s.source_number)
                store.save_case(engine_case, title="Inbound call intake",
                                client_party_id=party_id)
        db.insert("call_sessions", {
            "id": s.id, "tenant_id": s.tenant_id, "case_id": s.case_id,
            "direction": s.direction, "source_number": s.source_number,
            "destination_number": s.destination_number,
            "provider": s.provider, "status": s.status,
            "outcome": s.outcome, "outcome_reason": s.outcome_reason,
            "disposition_confidence": s.disposition_confidence,
            "recording_allowed": int(s.recording_allowed),
            "human_handoff_required": int(s.human_handoff_required),
            "started_at": str(s.started_at), "ended_at": str(s.ended_at)})
        return {"call_id": s.id, "case_id": s.case_id,
                "disposition": r.disposition, "handoff": r.handoff,
                "provider_is_mock": True}

    @app.post("/telephony/outbound/request")
    async def telephony_outbound(body: dict,
                                 user: dict = Depends(current_user)):
        require_role(user, "owner", "manager", "operator")
        contact = ContactCallState(**body.get("contact_state", {}))
        r = tele.request_outbound(
            tenant_id=user["tid"], case_id=body.get("case_id"),
            destination=body.get("destination", "+48600000000"),
            contact=contact,
            business_purpose=body.get("reason", ""),
            scenario=body.get("scenario", "answered"),
            urgent=bool(body.get("urgent")))
        s = r.session
        db.insert("call_sessions", {
            "id": s.id, "tenant_id": s.tenant_id, "case_id": s.case_id,
            "direction": s.direction, "source_number": s.source_number,
            "destination_number": s.destination_number,
            "provider": s.provider, "status": s.status,
            "outcome": s.outcome, "outcome_reason": s.outcome_reason,
            "disposition_confidence": s.disposition_confidence,
            "recording_allowed": int(s.recording_allowed),
            "human_handoff_required": int(s.human_handoff_required),
            "started_at": str(s.started_at), "ended_at": str(s.ended_at)})
        return {"call_id": s.id, "permission": r.permission,
                "disposition": r.disposition,
                "blocked_reason": r.blocked_reason, "retry": r.retry,
                "provider_is_mock": True}

    @app.get("/telephony/calls")
    async def telephony_calls(user: dict = Depends(current_user)):
        return [dict(r) for r in db.all(
            "SELECT * FROM call_sessions WHERE tenant_id=? "
            "ORDER BY created_at DESC", user["tid"])]

    # ---- admin / RBAC wiring (RbacEngine is authoritative server-side) --------------
    from ..admin.rbac import ROLE_PERMISSIONS, RbacEngine, ServiceAccount
    rbac = RbacEngine(audit)
    app.state.rbac = rbac

    def rbac_user_id(user: dict) -> str:
        """Map portal users into the RbacEngine (seeded on first touch)."""
        uid = f"portal-{user['uid']}"
        if uid not in rbac.users:
            from ..admin.rbac import User as RbacUser, Membership
            rbac.users[uid] = RbacUser(email=uid, name=user["role"], id=uid)
            rbac.memberships.append(Membership(
                tenant_id=user["tid"], user_id=uid, role=user["role"]))
        return uid

    def require_permission(user: dict, action: str) -> str:
        """Deny-by-default server-side gate through the RbacEngine (which
        also audits every decision as ACCESS_DECISION)."""
        uid = rbac_user_id(user)
        d = rbac.access(actor_type="user", actor_id=uid,
                        tenant_id=user["tid"], action=action)
        if d.decision != "ALLOW":
            raise HTTPException(403, "; ".join(d.reasons))
        return uid

    @app.get("/admin/me")
    async def admin_me(user: dict = Depends(current_user)):
        uid = rbac_user_id(user)
        m = rbac.membership_of(uid, user["tid"])
        return {"tenant_id": user["tid"], "role": m.role,
                "permissions": sorted(ROLE_PERMISSIONS[m.role])}

    @app.get("/admin/users")
    async def admin_users(user: dict = Depends(current_user)):
        require_permission(user, "tenant.manage_users")
        return [{"id": r["id"], "email": r["email"], "role": r["role"]}
                for r in db.all("SELECT * FROM users WHERE tenant_id=?",
                                user["tid"])]

    @app.post("/admin/users/invite")
    async def admin_invite(body: dict, user: dict = Depends(current_user)):
        uid = rbac_user_id(user)
        if body.get("role", "viewer") not in ROLE_PERMISSIONS:
            raise HTTPException(400, "unknown role")
        try:
            inv = rbac.invite(tenant_id=user["tid"],
                              email=body.get("email", ""),
                              role=body.get("role", "viewer"),
                              actor_user_id=uid, now=datetime.utcnow())
        except PermissionError as e:
            raise HTTPException(403, str(e))
        return {"invitation_id": inv.id, "status": inv.status}

    @app.patch("/admin/memberships/{target_user_id}/role")
    async def admin_change_role(target_user_id: str, body: dict,
                                user: dict = Depends(current_user)):
        # change_role's own guards cover escalation + last-owner, but the
        # base permission must be enforced here: without it a viewer could
        # demote a manager to viewer (viewer ⊆ viewer passes escalation).
        uid = require_permission(user, "tenant.manage_users")
        new_role = body.get("role")
        if new_role not in ROLE_PERMISSIONS:
            raise HTTPException(400, "unknown or missing role")
        target = rbac.membership_of(f"portal-{target_user_id}", user["tid"])
        if target is None:
            # Materialize the target portal user into rbac first.
            row = db.one("SELECT * FROM users WHERE id=? AND tenant_id=?",
                         target_user_id, user["tid"])
            if row is None:
                raise HTTPException(404, "user not found")
            fake = {"uid": target_user_id, "tid": user["tid"],
                    "role": row["role"]}
            rbac_user_id(fake)
            target = rbac.membership_of(f"portal-{target_user_id}",
                                        user["tid"])
        try:
            rbac.change_role(target.id, new_role, actor_user_id=uid)
        except PermissionError as e:
            raise HTTPException(403, str(e))
        db.update("users", target_user_id, {"role": new_role})
        return {"role": new_role}

    @app.get("/admin/access-logs")
    async def admin_access_logs(user: dict = Depends(current_user)):
        require_permission(user, "access_log.view")
        rows = [e for e in audit.events(event_type="ACCESS_DECISION")
                if (e.payload or {}).get("tenant_id") == user["tid"]]
        return [{"event_type": e.event_type, "actor": e.actor,
                 "payload": e.payload, "created_at": e.created_at}
                for e in rows[-50:]]

    # ---- governance visibility (redacted traces from audit) --------------------------
    def tenant_owns_event(e, tid: str) -> bool:
        """Tenant isolation for shared audit streams: an event belongs to
        the caller when its payload names their tenant or its case does."""
        if (e.payload or {}).get("tenant_id") == tid:
            return True
        if e.case_id:
            row = db.one("SELECT id FROM cases WHERE id=? AND tenant_id=?",
                         e.case_id, tid)
            return row is not None
        return False

    @app.get("/governance/traces")
    async def governance_traces(user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        rows = [e for e in audit.events(event_type="AGENT_TRACE")
                if tenant_owns_event(e, user["tid"])]
        return [{"payload": e.payload, "created_at": e.created_at}
                for e in rows[-50:]]

    @app.get("/governance/blocked")
    async def governance_blocked(user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        out = []
        for e in audit.events():
            if e.event_type in ("AGENT_TRACE", "CALL_PERMISSION_CHECKED",
                                "FOLLOW_UP_RATE_LIMITED",
                                "CALL_BLOCKED_ANTI_HARASSMENT",
                                "WORKFLOW_STOPPED_WASTE"):
                p = e.payload or {}
                status = p.get("status") or p.get("result") or ""
                if ("BLOCK" in str(status) or e.event_type in (
                        "FOLLOW_UP_RATE_LIMITED",
                        "CALL_BLOCKED_ANTI_HARASSMENT",
                        "WORKFLOW_STOPPED_WASTE")) \
                        and tenant_owns_event(e, user["tid"]):
                    out.append({"event": e.event_type, "detail": p,
                                "explanation": _explain_block(e)})
        return out[-30:]

    def _explain_block(e) -> str:
        p = e.payload or {}
        if e.event_type == "FOLLOW_UP_RATE_LIMITED":
            return ("Follow-up was not sent because the contact limit or "
                    "cooldown for this case was reached.")
        if e.event_type == "CALL_BLOCKED_ANTI_HARASSMENT":
            return ("Outbound call blocked to protect the client "
                    f"relationship ({p.get('reason', 'limit')}).")
        if e.event_type == "WORKFLOW_STOPPED_WASTE":
            return ("AI stopped this workflow because it was repeating "
                    "actions without new information.")
        status = str(p.get("status") or p.get("result") or "")
        if "HARD_BLOCKER" in status:
            return ("Action blocked by a non-negotiable safety rule "
                    "(for example: the client opted out or is on the "
                    "do-not-call list).")
        if "PERMISSION" in status:
            return ("Action blocked because the AI agent does not have "
                    "permission to do this.")
        reasons = p.get("reasons") or [p.get("reason", "policy")]
        return "Action blocked: " + ", ".join(str(r) for r in reasons)

    # ---- scheduling wiring ---------------------------------------------------------------
    from ..scheduling.engine import APPOINTMENT_TYPES, SchedulingEngine
    from .scheduling_store import SchedulingStore
    sched = SchedulingEngine(audit)
    sstore = SchedulingStore(db)
    sstore.hydrate(sched)      # migration v4: DB is the source of truth
    app.state.scheduling, app.state.scheduling_store = sched, sstore

    def tenant_scoped(tid: str, ident: Optional[str]) -> Optional[str]:
        """The mock engine's calendars are process-global; namespacing the
        user/resource ids per tenant keeps tenant A's 'tech-1' a different
        calendar from tenant B's 'tech-1'."""
        return f"{tid}::{ident}" if ident else None

    @app.get("/scheduling/availability")
    async def sched_availability(appointment_type: str = "VIDEO_CALL",
                                 day: Optional[str] = None,
                                 resource_id: Optional[str] = None,
                                 user_: dict = Depends(current_user)):
        if appointment_type not in APPOINTMENT_TYPES:
            raise HTTPException(400, "unknown appointment type")
        try:
            d = datetime.fromisoformat(day) if day else \
                datetime.utcnow() + timedelta(days=1)
        except ValueError:
            raise HTTPException(400, "invalid day")
        slots = sched.available_slots(
            day=d, appointment_type=appointment_type,
            resource_id=tenant_scoped(user_["tid"], resource_id))
        return json.loads(json.dumps(slots, default=str))

    @app.post("/scheduling/appointments")
    async def sched_book(body: dict, user: dict = Depends(current_user)):
        require_role(user, "owner", "manager", "operator")
        if not body.get("case_id") or not body.get("start_at"):
            raise HTTPException(400, "case_id and start_at are required")
        appt_type = body.get("appointment_type", "CALLBACK")
        if appt_type not in APPOINTMENT_TYPES:
            raise HTTPException(400, "unknown appointment type")
        try:
            start_at = datetime.fromisoformat(body["start_at"])
        except ValueError:
            raise HTTPException(400, "invalid start_at")
        case = load_case_or_404(body["case_id"], user)
        vector = load_vector(case.id)
        try:
            appt, token = sched.book(
                tenant_id=user["tid"], case_id=case.id,
                appointment_type=appt_type, start_at=start_at,
                user_id=tenant_scoped(user["tid"], body.get("user_id")),
                resource_id=tenant_scoped(user["tid"],
                                          body.get("resource_id")),
                vector=vector)
        except ValueError as e:
            raise HTTPException(409, str(e))
        save_vector(case.id, vector)
        sstore.save(appt, actor=user["uid"], event_type="BOOKED",
                    payload={"type": appt.appointment_type})
        return {"appointment_id": appt.id, "status": appt.status,
                "video_meeting_url": appt.video_meeting_url,
                "confirmation_url": f"/confirm/{token}" if token else None,
                "provider_is_mock": True}

    @app.get("/scheduling/appointments")
    async def sched_list(user: dict = Depends(current_user)):
        return [{"id": a.id, "case_id": a.case_id,
                 "type": a.appointment_type, "status": a.status,
                 "start_at": str(a.start_at)}
                for a in sched.appointments.values()
                if a.tenant_id == user["tid"]]

    @app.post("/scheduling/appointments/{appt_id}/{op}")
    async def sched_op(appt_id: str, op: str,
                       body: Optional[dict] = None,
                       user: dict = Depends(current_user)):
        body = body or {}
        require_role(user, "owner", "manager", "operator")
        appt = sched.appointments.get(appt_id)
        if appt is None or appt.tenant_id != user["tid"]:
            raise HTTPException(404, "appointment not found")
        vector = load_vector(appt.case_id)
        try:
            if op == "reschedule":
                if not body.get("new_start"):
                    raise HTTPException(400, "new_start required")
                sched.reschedule(appt_id, new_start=datetime.fromisoformat(
                    body["new_start"]), actor=user["uid"])
            elif op == "cancel":
                sched.cancel(appt_id, reason=body.get("reason", ""),
                             by=body.get("by", "company"))
            elif op == "complete":
                sched.complete(appt_id, vector=vector)
                save_vector(appt.case_id, vector)
                # Completion Loop runs after appointment events.
                case = store.load_case(appt.case_id, tenant_id=user["tid"])
                if case is not None:
                    loop.run_case(case, now=datetime.utcnow())
                    store.save_case(case)
            elif op == "no-show":
                sched.no_show(appt_id)
                case = store.load_case(appt.case_id, tenant_id=user["tid"])
                if case is not None:
                    loop.run_case(case, now=datetime.utcnow())
                    store.save_case(case)
            else:
                raise HTTPException(404, "unknown operation")
        except ValueError as e:
            raise HTTPException(409, str(e))
        sstore.save(appt, actor=user["uid"], event_type=op.upper(),
                    payload={"status": appt.status})
        return {"status": appt.status,
                "lifecycle_view": load_vector(appt.case_id)
                .derived_outcome_view()}

    @app.get("/confirm/{token}", response_class=HTMLResponse)
    async def confirm_page(token: str):
        from .ui import STYLE
        return (f"<!doctype html><html><head><meta charset='utf-8'>"
                f"<title>Confirm appointment</title><style>{STYLE}</style>"
                f"</head><body><h1>Confirm your appointment</h1>"
                f"<button id='confirm-btn'>Confirm</button>"
                f"<p id='done' class='ok' hidden>Confirmed — see you then!"
                f"</p><p id='fail' class='err' hidden>Link invalid or "
                f"expired.</p><script>"
                f"document.getElementById('confirm-btn').onclick=async()=>"
                f"{{const r=await fetch('/scheduling/confirm/{token}',"
                f"{{method:'POST'}});"
                f"document.getElementById(r.ok?'done':'fail').hidden=false;"
                f"if(r.ok)document.getElementById('confirm-btn').hidden"
                f"=true;}};</script></body></html>")

    @app.post("/scheduling/confirm/{token}")
    async def sched_confirm(token: str):
        appt = sched.confirm(token, now=datetime.utcnow())
        if appt is None:
            # The engine may have flipped the appointment to EXPIRED —
            # persist that state change before answering with a safe 404.
            import hashlib as _hashlib
            appt_id = sstore.appointment_id_for_token_hash(
                _hashlib.sha256(token.encode()).hexdigest())
            if appt_id and appt_id in sched.appointments:
                sstore.save(sched.appointments[appt_id], actor="client",
                            event_type="CONFIRM_REJECTED",
                            payload={"reason": "invalid_or_expired"})
            raise HTTPException(404, "invalid or expired")
        sstore.save(appt, actor="client", event_type="CONFIRMED")
        return {"status": appt.status}

    # ---- quotes (Quote Builder Q-B: persistence + API over the Q-A engine) ----
    from decimal import Decimal, InvalidOperation

    from ..quotes.engine import QuoteEngine
    from ..quotes.models import (AcceptanceEvidence, IllegalQuoteTransition,
                                 PaymentMilestone, PaymentSchedule,
                                 PriceBook, PriceBookItem, PricingRule,
                                 QuoteImmutableError, QuoteLineItem,
                                 quote_transition)
    from ..quotes.pricing import calculate_quote
    from ..quotes.providers import (MockInvoiceHandoffProvider,
                                    MockPdfProvider)
    from ..quotes.scores import evidence_coverage_score
    from .quote_store import QuoteStore

    qstore = QuoteStore(db)
    qengine = QuoteEngine(audit)
    qpdf = MockPdfProvider()
    qhandoff = MockInvoiceHandoffProvider()
    app.state.quotes, app.state.quote_store = qengine, qstore

    def load_quote_or_404(quote_id: str, user: dict):
        q = qstore.load_quote(quote_id, tenant_id=user["tid"])
        if q is None:
            raise HTTPException(404, "quote not found")  # incl. cross-tenant
        qengine.quotes[q.id] = q
        return q

    def hydrate_approvals(quote_id: str, user: dict) -> None:
        qengine.approvals = qstore.load_approvals(quote_id,
                                                  tenant_id=user["tid"])

    def persist_approvals(user: dict) -> None:
        for req in qengine.approvals:
            qstore.save_approval(user["tid"], req)

    _LINE_DEC = ["quantity", "material_cost", "labor_cost",
                 "subcontractor_cost", "travel_cost", "permit_cost",
                 "overhead_allocation", "risk_contingency",
                 "requested_discount"]
    _LINE_OPT_DEC = ["price_book_price", "manual_price"]

    def parse_line(body: dict) -> QuoteLineItem:
        if not str(body.get("description", "")).strip():
            raise HTTPException(400, "line item needs a description")
        kw = {}
        try:
            for f in _LINE_DEC:
                if f in body:
                    kw[f] = Decimal(str(body[f]))
            for f in _LINE_OPT_DEC:
                if body.get(f) is not None:
                    kw[f] = Decimal(str(body[f]))
        except (InvalidOperation, ValueError):
            raise HTTPException(400, "invalid number in line item")
        return QuoteLineItem(
            description=body["description"], sku=body.get("sku"),
            discount_reason=body.get("discount_reason", ""),
            is_free_item=bool(body.get("is_free_item")),
            cost_known=bool(body.get("cost_known", True)),
            cost_age_days=int(body.get("cost_age_days", 0)),
            tax_category=body.get("tax_category", "standard"),
            is_custom=bool(body.get("is_custom")),
            created_by=body.get("created_by", "human"), **kw)

    def quote_json(q) -> dict:
        return {
            "id": q.id, "case_id": q.case_id, "state": q.state,
            "version": q.version, "revised_from_id": q.revised_from_id,
            "currency": q.currency, "created_by": q.created_by,
            "editable": q.editable,
            "subtotal": str(q.subtotal), "tax_total": str(q.tax_total),
            "total": str(q.total),
            "valid_until": str(q.valid_until) if q.valid_until else None,
            "assumptions": q.assumptions, "exclusions": q.exclusions,
            "terms_template_approved": q.terms_template_approved,
            "tax_engine_is_mock": True,
            "line_items": [{
                "id": li.id, "description": li.description,
                "sku": li.sku, "quantity": str(li.quantity),
                "line_cost": str(li.line_cost),
                "price_before_discount": str(li.price_before_discount),
                "applied_discount": str(li.applied_discount),
                "price_after_discount": str(li.price_after_discount),
                "margin_percent": str(li.margin_percent)
                if li.margin_percent is not None else None,
                "line_total": str(li.line_total),
                "requires_human_review": li.requires_human_review,
            } for li in q.line_items],
            "payment_schedule": [
                {"label": m.label, "fraction": str(m.fraction),
                 "trigger": m.trigger, "is_deposit": m.is_deposit,
                 "blocks_fulfillment_until_paid":
                     m.blocks_fulfillment_until_paid}
                for m in q.payment_schedule.milestones]
            if q.payment_schedule else [],
        }

    def gates_json(gates: dict) -> dict:
        return {name: {"decision": g.decision, "reasons": g.reasons,
                       "hard_blockers": g.hard_blockers}
                for name, g in gates.items()}

    @app.get("/quotes")
    async def list_quotes(case_id: Optional[str] = None,
                          user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return qstore.list_quotes(tenant_id=user["tid"], case_id=case_id)

    @app.post("/quotes")
    async def create_quote(body: dict,
                           user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        if not body.get("case_id"):
            raise HTTPException(400, "case_id is required")
        case = load_case_or_404(body["case_id"], user)
        row = db.one("SELECT client_party_id FROM cases WHERE id=?",
                     case.id)
        q = qengine.create_draft(
            tenant_id=user["tid"], case_id=case.id,
            customer_party_id=body.get("customer_party_id")
            or (row["client_party_id"] if row else None),
            created_by=user["uid"],
            currency=body.get("currency", "EUR"))
        qstore.save_quote(q)
        return quote_json(q)

    @app.get("/quotes/{quote_id}")
    async def get_quote(quote_id: str,
                        user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return quote_json(load_quote_or_404(quote_id, user))

    @app.patch("/quotes/{quote_id}")
    async def patch_quote(quote_id: str, body: dict,
                          user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        q = load_quote_or_404(quote_id, user)
        if q.state == "PRICE_CALCULATED":     # edits invalidate the calc
            quote_transition(q, "DRAFT")
        try:
            q.assert_editable()
        except QuoteImmutableError as e:
            raise HTTPException(409, str(e))
        for f in ("assumptions", "exclusions", "terms_template_id",
                  "custom_terms_text", "customer_party_id"):
            if f in body:
                setattr(q, f, body[f])
        if "terms_template_approved" in body:
            q.terms_template_approved = bool(body["terms_template_approved"])
        if "cost_volatility" in body:
            q.cost_volatility = float(body["cost_volatility"])
        qstore.save_quote(q)
        return quote_json(q)

    @app.post("/quotes/{quote_id}/lines")
    async def add_quote_line(quote_id: str, body: dict,
                             user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        q = load_quote_or_404(quote_id, user)
        if q.state == "PRICE_CALCULATED":     # edits invalidate the calc
            quote_transition(q, "DRAFT")
        try:
            qengine.add_line(q, parse_line(body))
        except QuoteImmutableError as e:
            raise HTTPException(409, str(e))
        qstore.save_quote(q)
        return quote_json(q)

    @app.post("/quotes/{quote_id}/calculate")
    async def calculate_quote_api(quote_id: str, body: Optional[dict] = None,
                                  user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        body = body or {}
        q = load_quote_or_404(quote_id, user)
        if q.state == "PRICE_CALCULATED":     # recalculation is legal
            quote_transition(q, "DRAFT")
        book = qstore.default_price_book(user["tid"])
        rules = qstore.load_pricing_rules(user["tid"])
        try:
            qengine.calculate(q, price_book=book, pricing_rules=rules,
                              now=datetime.utcnow())
        except QuoteImmutableError as e:
            raise HTTPException(409, str(e))
        gates = qengine.evaluate_gates(
            q, readiness_context=body.get("readiness") or {},
            feasibility_context=body.get("feasibility"))
        qstore.save_quote(q)
        ev = q.evidence
        return {**quote_json(q), "gates": gates_json(gates), "scores": {
            "price_confidence": round(qengine.price_confidence(q), 4),
            "evidence_coverage": round(evidence_coverage_score(
                required_facts_covered=ev.required_facts_covered,
                source_reliability=ev.source_reliability,
                evidence_recency=ev.evidence_recency,
                scope_consistency=ev.scope_consistency,
                human_verified_facts=ev.human_verified_facts,
                pricing_data_coverage=ev.pricing_data_coverage), 4)}}

    @app.post("/quotes/{quote_id}/approve")
    async def approve_quote(quote_id: str,
                            user: dict = Depends(current_user)):
        require_permission(user, "offer.approve")
        q = load_quote_or_404(quote_id, user)
        hydrate_approvals(quote_id, user)
        try:
            qengine.approve(q, approver_id=user["uid"])
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except IllegalQuoteTransition as e:
            raise HTTPException(409, str(e))
        persist_approvals(user)
        qstore.save_quote(q)
        return quote_json(q)

    @app.post("/quotes/{quote_id}/reject")
    async def reject_quote(quote_id: str, body: dict,
                           user: dict = Depends(current_user)):
        require_permission(user, "offer.approve")
        if not str(body.get("reason", "")).strip():
            raise HTTPException(400, "rejection requires a reason")
        q = load_quote_or_404(quote_id, user)
        try:
            quote_transition(q, "REJECTED_BY_APPROVER")
        except IllegalQuoteTransition as e:
            raise HTTPException(409, str(e))
        for req in qstore.load_approvals(quote_id, tenant_id=user["tid"]):
            if req.status == "PENDING":
                req.status = "REJECTED"
                req.approver_id = user["uid"]
                qstore.save_approval(user["tid"], req)
        audit.append(event_type="QUOTE_REJECTED_BY_APPROVER",
                     actor=user["uid"], case_id=q.case_id,
                     payload={"quote_id": q.id,
                              "reason": body["reason"]})
        qstore.save_quote(q)
        return quote_json(q)

    @app.post("/quotes/{quote_id}/send")
    async def send_quote(quote_id: str, body: Optional[dict] = None,
                         user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        body = body or {}
        q = load_quote_or_404(quote_id, user)
        if q.revised_from_id:      # supersede path needs the ancestor
            old = qstore.load_quote(q.revised_from_id,
                                    tenant_id=user["tid"])
            if old is not None:
                qengine.quotes[old.id] = old
        hydrate_approvals(quote_id, user)
        try:
            result = qengine.send(
                q, actor_type="human",
                readiness_context=body.get("readiness") or {},
                feasibility_context=body.get("feasibility"),
                now=datetime.utcnow())
        except IllegalQuoteTransition as e:
            raise HTTPException(409, str(e))
        if result.decision != "SENT":
            raise HTTPException(409, "; ".join(result.reasons))
        qstore.save_quote(q)
        if q.revised_from_id and q.revised_from_id in qengine.quotes:
            qstore.save_quote(qengine.quotes[q.revised_from_id])
        return {**quote_json(q), "send_result": result.decision}

    @app.post("/quotes/{quote_id}/accept")
    async def accept_quote(quote_id: str, body: Optional[dict] = None,
                           user: dict = Depends(current_user)):
        """Demo/simulated client acceptance. Creates payment/invoice/
        fulfillment REQUIREMENT placeholders — never completes the case."""
        require_permission(user, "offer.create")
        body = body or {}
        q = load_quote_or_404(quote_id, user)
        channel = body.get("channel", "portal_click")
        evidence = None
        if body.get("evidence"):
            e = body["evidence"]
            if not e.get("kind") or not e.get("reference_id"):
                raise HTTPException(400, "evidence needs kind and "
                                         "reference_id")
            evidence = AcceptanceEvidence(kind=e["kind"],
                                          reference_id=e["reference_id"],
                                          recorded_by=user["uid"],
                                          note=e.get("note", ""))
        elif channel != "portal_click":
            raise HTTPException(400, "manual acceptance requires "
                                     "AcceptanceEvidence")
        try:
            reqs = qengine.accept(q, channel=channel, evidence=evidence,
                                  now=datetime.utcnow())
        except IllegalQuoteTransition as e:
            raise HTTPException(409, str(e))
        except ValueError as e:
            qstore.save_quote(q)              # EXPIRED state persists
            raise HTTPException(409, str(e))
        qstore.save_quote(q)
        qstore.save_payment_requirements(user["tid"], reqs)
        # Lifecycle: deal accepted, money + delivery OPEN (mock providers).
        v = load_vector(q.case_id)
        v.deal = DealState.ACCEPTED_BY_CLIENT
        v.transaction = TransactionState.INVOICE_REQUIRED
        v.fulfillment = FulfillmentState.REQUIRED
        save_vector(q.case_id, v)
        handoff = qhandoff.handoff(q, reqs)
        audit.append(event_type="INVOICE_HANDOFF_PREPARED",
                     actor="mock-invoice-handoff", case_id=q.case_id,
                     payload=handoff)
        return {**quote_json(q),
                "payment_requirements": [
                    {"label": r.label, "amount": str(r.amount),
                     "trigger": r.trigger,
                     "blocks_fulfillment_until_paid":
                         r.blocks_fulfillment_until_paid} for r in reqs],
                "invoice_handoff": handoff,
                "lifecycle_view": v.derived_outcome_view(),
                "case_completed": False}

    @app.post("/quotes/{quote_id}/decline")
    async def decline_quote(quote_id: str, body: dict,
                            user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        if not str(body.get("reason", "")).strip():
            raise HTTPException(400, "declining requires a reason")
        q = load_quote_or_404(quote_id, user)
        try:
            qengine.decline(q, reason=body["reason"])
        except IllegalQuoteTransition as e:
            raise HTTPException(409, str(e))
        qstore.save_quote(q)
        return quote_json(q)

    @app.post("/quotes/{quote_id}/expire")
    async def expire_quote(quote_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        q = load_quote_or_404(quote_id, user)
        try:
            quote_transition(q, "EXPIRED")
        except IllegalQuoteTransition as e:
            raise HTTPException(409, str(e))
        audit.append(event_type="QUOTE_EXPIRED", actor=user["uid"],
                     case_id=q.case_id, payload={"quote_id": q.id})
        qstore.save_quote(q)
        return quote_json(q)

    @app.post("/quotes/{quote_id}/revise")
    async def revise_quote(quote_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        q = load_quote_or_404(quote_id, user)
        try:
            new = qengine.revise(q, revised_by=user["uid"])
        except (QuoteImmutableError, IllegalQuoteTransition) as e:
            raise HTTPException(409, str(e))
        qstore.save_quote(q)
        qstore.save_quote(new)
        return quote_json(new)

    @app.post("/quotes/{quote_id}/generate-pdf")
    async def generate_quote_pdf(quote_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        q = load_quote_or_404(quote_id, user)
        html = qpdf.render(q)
        doc_id = str(uuid.uuid4())
        db.insert("quote_pdf_documents", {
            "id": doc_id, "tenant_id": user["tid"], "quote_id": q.id,
            "html": html, "is_mock": 1})
        audit.append(event_type="QUOTE_DOCUMENT_GENERATED",
                     actor="mock-pdf", case_id=q.case_id,
                     payload={"quote_id": q.id, "document_id": doc_id,
                              "is_mock": True})
        return {"document_id": doc_id, "is_mock": True,
                "provider": qpdf.name, "html": html}

    @app.get("/quotes/{quote_id}/events")
    async def quote_events(quote_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        load_quote_or_404(quote_id, user)
        return [{"event_type": e.event_type, "actor": e.actor,
                 "payload": e.payload, "created_at": e.created_at}
                for e in audit.events()
                if (e.payload or {}).get("quote_id") == quote_id]

    @app.get("/quotes/{quote_id}/evidence")
    async def quote_evidence(quote_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        q = load_quote_or_404(quote_id, user)
        ev = q.evidence
        import dataclasses as _dc
        return {"bundle": _dc.asdict(ev),
                "evidence_coverage_score": round(evidence_coverage_score(
                    required_facts_covered=ev.required_facts_covered,
                    source_reliability=ev.source_reliability,
                    evidence_recency=ev.evidence_recency,
                    scope_consistency=ev.scope_consistency,
                    human_verified_facts=ev.human_verified_facts,
                    pricing_data_coverage=ev.pricing_data_coverage), 4)}

    @app.get("/quotes/{quote_id}/payment-schedule")
    async def get_payment_schedule(quote_id: str,
                                   user: dict = Depends(current_user)):
        require_permission(user, "payment.view")
        q = load_quote_or_404(quote_id, user)
        return {"milestones": quote_json(q)["payment_schedule"],
                "payment_requirements": qstore.load_payment_requirements(
                    quote_id, tenant_id=user["tid"])}

    @app.post("/quotes/{quote_id}/payment-schedule")
    async def set_payment_schedule(quote_id: str, body: dict,
                                   user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        q = load_quote_or_404(quote_id, user)
        try:
            schedule = PaymentSchedule(milestones=[
                PaymentMilestone(
                    label=m["label"], fraction=Decimal(str(m["fraction"])),
                    trigger=m.get("trigger", "on_acceptance"),
                    is_deposit=bool(m.get("is_deposit")),
                    blocks_fulfillment_until_paid=bool(
                        m.get("blocks_fulfillment_until_paid")))
                for m in body.get("milestones", [])])
        except (KeyError, InvalidOperation):
            raise HTTPException(400, "invalid milestone payload")
        if q.state == "PRICE_CALCULATED":     # edits invalidate the calc
            quote_transition(q, "DRAFT")
        try:
            qengine.set_payment_schedule(q, schedule)
        except QuoteImmutableError as e:
            raise HTTPException(409, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        qstore.save_quote(q)
        return quote_json(q)

    @app.get("/quotes/{quote_id}/change-orders")
    async def list_change_orders(quote_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_quote_or_404(quote_id, user)
        return qstore.load_change_orders(quote_id, tenant_id=user["tid"])

    @app.post("/quotes/{quote_id}/change-orders")
    async def create_change_order(quote_id: str, body: dict,
                                  user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        q = load_quote_or_404(quote_id, user)
        if not str(body.get("description", "")).strip() \
                or "price_delta" not in body:
            raise HTTPException(400, "description and price_delta required")
        try:
            price_delta = Decimal(str(body["price_delta"]))
            cost_delta = Decimal(str(body.get("cost_delta", "0")))
        except InvalidOperation:
            raise HTTPException(400, "invalid amount")
        try:
            co = qengine.create_change_order(
                q, description=body["description"],
                price_delta=price_delta, cost_delta=cost_delta,
                reason=body.get("reason", ""), requested_by=user["uid"])
        except ValueError as e:
            raise HTTPException(409, str(e))
        # Recalculated margin on the delta — same math as line margins.
        from ..quotes.pricing import margin_percent as _margin
        co_margin = _margin(co.price_delta, co.cost_delta) \
            if co.price_delta > Decimal("0") else None
        qstore.save_change_order(user["tid"], co, margin_percent=co_margin)
        return {"id": co.id, "status": co.status,
                "price_delta": str(co.price_delta),
                "cost_delta": str(co.cost_delta),
                "margin_percent": str(co_margin)
                if co_margin is not None else None,
                "requires_approval": True}

    # -- price books & pricing rules --------------------------------------------
    @app.get("/price-books")
    async def list_price_books(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return [dict(r) for r in db.all(
            "SELECT id, name, currency FROM price_books WHERE tenant_id=?",
            user["tid"])]

    @app.post("/price-books")
    async def create_price_book(body: dict,
                                user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        book = PriceBook(tenant_id=user["tid"],
                         name=body.get("name", "default"),
                         currency=body.get("currency", "EUR"))
        qstore.save_price_book(book)
        return {"id": book.id, "name": book.name}

    @app.get("/price-books/{book_id}/items")
    async def list_price_book_items(book_id: str,
                                    user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        book = qstore.load_price_book(book_id, tenant_id=user["tid"])
        if book is None:
            raise HTTPException(404, "price book not found")
        return [{"sku": i.sku, "name": i.name,
                 "list_price": str(i.list_price),
                 "tax_category": i.tax_category}
                for i in book.items.values()]

    @app.post("/price-books/{book_id}/items")
    async def add_price_book_item(book_id: str, body: dict,
                                  user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        book = qstore.load_price_book(book_id, tenant_id=user["tid"])
        if book is None:
            raise HTTPException(404, "price book not found")
        if not body.get("sku") or "list_price" not in body:
            raise HTTPException(400, "sku and list_price required")
        try:
            item = PriceBookItem(
                sku=body["sku"], name=body.get("name", body["sku"]),
                list_price=Decimal(str(body["list_price"])),
                cost_hint=Decimal(str(body["cost_hint"]))
                if body.get("cost_hint") is not None else None,
                tax_category=body.get("tax_category", "standard"))
        except InvalidOperation:
            raise HTTPException(400, "invalid price")
        qstore.save_price_book_item(book, item)
        return {"sku": item.sku, "list_price": str(item.list_price)}

    @app.get("/pricing-rules")
    async def list_pricing_rules(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return [{"id": r.id, "name": r.name,
                 "applies_to_sku": r.applies_to_sku,
                 "min_quantity": str(r.min_quantity),
                 "discount_percent": str(r.discount_percent),
                 "priority": r.priority}
                for r in qstore.load_pricing_rules(user["tid"])]

    @app.post("/pricing-rules")
    async def create_pricing_rule(body: dict,
                                  user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        if not body.get("name"):
            raise HTTPException(400, "name required")
        try:
            rule = PricingRule(
                tenant_id=user["tid"], name=body["name"],
                applies_to_sku=body.get("applies_to_sku", "*"),
                min_quantity=Decimal(str(body.get("min_quantity", "0"))),
                discount_percent=Decimal(str(
                    body.get("discount_percent", "0"))),
                priority=int(body.get("priority", 0)))
        except (InvalidOperation, ValueError):
            raise HTTPException(400, "invalid rule payload")
        qstore.save_pricing_rule(rule)
        return {"id": rule.id, "name": rule.name}

    @app.patch("/pricing-rules/{rule_id}")
    async def patch_pricing_rule(rule_id: str, body: dict,
                                 user: dict = Depends(current_user)):
        require_permission(user, "offer.create")
        row = db.one("SELECT * FROM pricing_rules WHERE id=? AND "
                     "tenant_id=?", rule_id, user["tid"])
        if row is None:
            raise HTTPException(404, "pricing rule not found")
        fields = {}
        for f in ("name", "applies_to_sku"):
            if f in body:
                fields[f] = body[f]
        for f in ("min_quantity", "discount_percent"):
            if f in body:
                fields[f] = str(Decimal(str(body[f])))
        if "priority" in body:
            fields["priority"] = int(body["priority"])
        if "active" in body:
            fields["active"] = int(bool(body["active"]))
        db.update("pricing_rules", rule_id, fields)
        return {"id": rule_id, **{k: str(v) for k, v in fields.items()}}

    # -- stateless pricing utilities ------------------------------------------------
    @app.post("/pricing/calculate")
    async def pricing_calculate(body: dict,
                                user: dict = Depends(current_user)):
        """Stateless what-if calculation (nothing persisted; mock tax)."""
        require_permission(user, "case.read")
        from ..quotes.models import Quote as _Quote
        q = _Quote(tenant_id=user["tid"], case_id="what-if")
        q.line_items = [parse_line(l) for l in body.get("lines", [])]
        if not q.line_items:
            raise HTTPException(400, "lines required")
        calculate_quote(q, target_margin=qengine.thresholds.target_margin,
                        max_auto_discount=qengine.thresholds
                        .max_auto_discount,
                        price_book=qstore.default_price_book(user["tid"]),
                        pricing_rules=qstore.load_pricing_rules(
                            user["tid"]))
        return {**quote_json(q), "persisted": False}

    @app.post("/pricing/validate")
    async def pricing_validate(body: dict,
                               user: dict = Depends(current_user)):
        """Stateless gate check for a hypothetical quote."""
        require_permission(user, "case.read")
        from ..quotes.models import Quote as _Quote
        q = _Quote(tenant_id=user["tid"], case_id="what-if",
                   customer_party_id="what-if")
        q.line_items = [parse_line(l) for l in body.get("lines", [])]
        if not q.line_items:
            raise HTTPException(400, "lines required")
        calculate_quote(q, target_margin=qengine.thresholds.target_margin,
                        max_auto_discount=qengine.thresholds
                        .max_auto_discount)
        gates = qengine.evaluate_gates(
            q, readiness_context=body.get("readiness") or {},
            feasibility_context=body.get("feasibility"))
        return {"gates": gates_json(gates), "persisted": False}

    # ---- Evidence Trust Fabric (V-B: zero-trust evidence API) ----------------
    import base64
    import tempfile
    from pathlib import Path as _Path

    from ..evidence.engine import (EvidenceEngine, EvidenceValidationError,
                                   RetentionContext)
    from ..evidence.models import (EvidenceSource,
                                   IllegalEvidenceTransition)
    from ..evidence.requirements import (REQUIREMENT_PROFILES,
                                         check_requirements)
    from ..evidence.storage import LocalEvidenceStorageProvider
    from ..evidence.views import (agent_view, causality_check, human_view,
                                  mark_symbol_human_verified)
    from .evidence_store import EvidenceStore
    from ..evidence.derivatives import generate_manifest
    from ..evidence.immutability import (RetentionPolicy,
                                         hard_delete_allowed,
                                         storage_worm_capability)
    from ..evidence.policy import (EvidencePolicyDriftReport,
                                   current_policy_version, policy_fingerprint)
    from ..evidence.rehydration import EvidenceRehydrator
    from ..evidence.scanners import (MockScannerProvider, ScaffoldCdrProvider,
                                     decide_file_treatment,
                                     scanner_risk_contribution)
    from ..evidence import transparency as _mrk
    from ..evidence import reports as _rpt

    vault_dir = tempfile.mkdtemp(prefix="finalis-evidence-") \
        if db_path == ":memory:" \
        else str(_Path(db_path).resolve().parent / "evidence-vault")
    evengine = EvidenceEngine(LocalEvidenceStorageProvider(vault_dir),
                              audit)
    estore = EvidenceStore(db)
    # V-E: rebuild live engine state from persisted facts (event-sourced).
    EvidenceRehydrator(estore).rehydrate(evengine)
    ev_scanner = MockScannerProvider()
    ev_cdr = ScaffoldCdrProvider()
    app.state.evidence, app.state.evidence_store = evengine, estore
    # Record the current evidence policy fingerprint once at startup.
    estore.save_policy_version(current_policy_version(),
                               policy_fingerprint(), created_at=utcnow())
    upload_sessions: dict[str, dict] = {}     # SCAFFOLDED_ONLY (future TUS)

    EVIDENCE_HONESTY = {
        "scanner": "MOCKED_AND_TESTED — deterministic mock verdict, not "
                   "production antivirus/CDR",
        "storage": "local vault (replaceable provider; no S3/MinIO/WORM "
                   "connected)",
        "ocr": "SCAFFOLDED_ONLY — no parser executes",
        "core_rule": "documents provide facts, never commands",
    }

    def load_evidence_or_404(evidence_id: str, user: dict):
        ev = evengine.objects.get(evidence_id)
        if ev is None or ev.tenant_id != user["tid"]:
            raise HTTPException(404, "evidence not found")  # incl. x-tenant
        return ev

    def evidence_json(ev) -> dict:
        return {"id": ev.id, "case_id": ev.case_id,
                "evidence_type": ev.evidence_type, "state": ev.state,
                "original_filename": ev.meta.original_filename,
                "extension": ev.meta.extension,
                "size_bytes": ev.meta.size_bytes,
                "declared_mime": ev.meta.declared_mime,
                "detected_mime": ev.meta.detected_mime,
                "mime_mismatch": ev.meta.mime_mismatch,
                "active_content": ev.meta.active_content,
                "sensitivity": ev.sensitivity,
                "injection_risk": round(ev.injection_risk, 4),
                "human_verified": ev.human_verified,
                "legal_hold": ev.legal_hold,
                "integrity": {"algorithm": ev.integrity.algorithm,
                              "sha256": ev.integrity.digest,
                              "valid": ev.integrity.valid}
                if ev.integrity else None,
                "scan": {"provider": ev.scan.provider,
                         "is_mock": ev.scan.is_mock,
                         "status": ev.scan.status},
                "untrusted": not all(s.trusted for s in ev.symbols)
                if ev.symbols else True,
                "honesty": EVIDENCE_HONESTY}

    @app.post("/evidence/upload")
    async def evidence_upload(body: dict,
                              user: dict = Depends(current_user)):
        """Quarantine-first ingest. JSON+base64 keeps the project's
        existing upload pattern (no multipart dependency). The client's
        Content-Type/extension are treated as claims, never trust."""
        require_permission(user, "document.upload")
        if not body.get("case_id") or not body.get("filename") \
                or "content_b64" not in body:
            raise HTTPException(400, "case_id, filename and content_b64 "
                                     "are required")
        case = load_case_or_404(body["case_id"], user)  # session tenant
        try:
            data = base64.b64decode(body["content_b64"])
        except Exception:
            raise HTTPException(400, "content_b64 is not valid base64")
        try:
            ev = evengine.ingest(
                tenant_id=user["tid"], case_id=case.id,
                uploaded_by=user["uid"],
                filename=str(body["filename"]),
                declared_mime=str(body.get("mime", "")), data=data,
                evidence_type=body.get("evidence_type", "document"),
                source=EvidenceSource(kind=body.get("source_kind",
                                                    "staff")),
                sensitivity=body.get("sensitivity", "normal"),
                text_preview=str(body.get("text_preview", "")))
        except EvidenceValidationError as e:
            raise HTTPException(400, str(e))
        estore.save(ev)
        return {**evidence_json(ev), "quarantine_first": True,
                "storage_capabilities":
                    evengine.storage.capabilities().__dict__}

    @app.get("/evidence")
    async def evidence_list(case_id: Optional[str] = None,
                            user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        return [{"id": r["id"], "case_id": r["case_id"],
                 "evidence_type": r["evidence_type"], "state": r["state"],
                 "original_filename": r["original_filename"],
                 "sensitivity": r["sensitivity"]}
                for r in estore.list(tenant_id=user["tid"],
                                     case_id=case_id)]

    @app.get("/evidence/profiles")
    async def evidence_profiles(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {name: {"required": p.required_types,
                       "min_trust": p.min_trust,
                       "human_verification_required":
                           p.human_verification_required}
                for name, p in REQUIREMENT_PROFILES.items()}

    @app.get("/evidence/storage-capabilities")
    async def evidence_storage_caps(user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        return {"provider": evengine.storage.name,
                "capabilities": evengine.storage.capabilities().__dict__,
                "note": "local vault — WORM/retention/versioning enforced "
                        "by the domain layer, not natively "
                        "(BLOCKED_BY_EXTERNAL_PROVIDER for S3/MinIO)"}

    # Static single-segment GET routes MUST be declared before the dynamic
    # /evidence/{evidence_id} route below, or they get shadowed. Their
    # bodies delegate to helpers defined later in create_app (closures
    # resolve at request time, after create_app has fully executed).
    @app.get("/evidence/contracts")
    async def evidence_contracts_list(case_id: Optional[str] = None,
                                      user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        return [_contract_json(r) for r in estore.contracts(
            tenant_id=user["tid"], case_id=case_id)]

    @app.get("/evidence/merkle-roots")
    async def evidence_merkle_list(user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        return [{"batch_id": r["id"], "root": r["root"],
                 "size": r["size"], "created_at": r["created_at"]}
                for r in estore.merkle_roots(tenant_id=user["tid"])]

    @app.get("/evidence/policy-version")
    async def evidence_policy_version(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"policy_version": current_policy_version(),
                "fingerprint": policy_fingerprint(),
                "requirement_profiles": sorted(REQUIREMENT_PROFILES)}

    # -- upload sessions (SCAFFOLDED_ONLY — future-TUS shape, no chunking) --
    @app.post("/evidence/upload-sessions")
    async def create_upload_session(body: dict,
                                    user: dict = Depends(current_user)):
        require_permission(user, "document.upload")
        if not body.get("case_id"):
            raise HTTPException(400, "case_id required")
        load_case_or_404(body["case_id"], user)
        sid = str(uuid.uuid4())
        upload_sessions[sid] = {
            "id": sid, "tenant_id": user["tid"],
            "case_id": body["case_id"],
            "expected_size": int(body.get("expected_size", 0)),
            "filename": body.get("filename", ""),
            "state": "CREATED",
            "expires_at": (datetime.utcnow()
                           + timedelta(hours=2)).isoformat(),
            "status": "SCAFFOLDED_ONLY",
            "note": "future resumable upload (TUS-compatible shape); "
                    "chunked PATCH not implemented — use "
                    "/evidence/upload"}
        return upload_sessions[sid]

    @app.get("/evidence/upload-sessions/{session_id}")
    async def get_upload_session(session_id: str,
                                 user: dict = Depends(current_user)):
        s = upload_sessions.get(session_id)
        if s is None or s["tenant_id"] != user["tid"]:
            raise HTTPException(404, "upload session not found")
        return s

    @app.delete("/evidence/upload-sessions/{session_id}")
    async def delete_upload_session(session_id: str,
                                    user: dict = Depends(current_user)):
        s = upload_sessions.get(session_id)
        if s is None or s["tenant_id"] != user["tid"]:
            raise HTTPException(404, "upload session not found")
        del upload_sessions[session_id]
        return {"deleted": True}

    @app.get("/evidence/{evidence_id}")
    async def evidence_detail(evidence_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        ev = load_evidence_or_404(evidence_id, user)
        if ev.sensitivity in ("sensitive", "legal"):
            require_permission(user, "document.view_sensitive")
        return evidence_json(ev)

    @app.get("/evidence/{evidence_id}/chain")
    async def evidence_chain(evidence_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        load_evidence_or_404(evidence_id, user)
        return estore.chain_events(evidence_id, tenant_id=user["tid"])

    @app.post("/evidence/{evidence_id}/verify-integrity")
    async def evidence_verify_integrity(evidence_id: str,
                                        user: dict = Depends(
                                            current_user)):
        require_permission(user, "document.analyze")
        ev = load_evidence_or_404(evidence_id, user)
        ok = evengine.verify_integrity(ev)
        estore.save(ev)
        return {"valid": ok, "state": ev.state,
                "sha256": ev.integrity.digest if ev.integrity else None}

    @app.post("/evidence/{evidence_id}/review")
    async def evidence_review(evidence_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_permission(user, "document.analyze")
        ev = load_evidence_or_404(evidence_id, user)
        verdict = body.get("verdict", "")
        try:
            if verdict == "SCANNED_CLEAN":
                # Mock scanner over the stored bytes — honestly labeled.
                evengine.run_scan(ev, evengine.storage.get_bytes(
                    ev.storage))
            elif verdict in ("ADMISSIBLE", "ADMISSIBLE_WITH_LIMITS",
                             "REJECTED", "NEEDS_HUMAN_REVIEW"):
                evengine.human_review(ev, reviewer=user["uid"],
                                      verdict=verdict,
                                      note=body.get("note", ""))
            else:
                raise HTTPException(400, "unknown verdict")
        except IllegalEvidenceTransition as e:
            raise HTTPException(409, str(e))
        estore.save(ev)
        return {**evidence_json(ev),
                "scanner_is_mock": ev.scan.is_mock}

    @app.post("/evidence/{evidence_id}/legal-hold")
    async def evidence_legal_hold(evidence_id: str, body: dict,
                                  user: dict = Depends(current_user)):
        require_permission(user, "override.compliance_review")
        ev = load_evidence_or_404(evidence_id, user)
        action = body.get("action", "place")
        if action == "place":
            if not str(body.get("reason", "")).strip():
                raise HTTPException(400, "legal hold requires a reason")
            hold = evengine.place_legal_hold(ev, reason=body["reason"],
                                             placed_by=user["uid"])
            estore.save_legal_hold(hold)
        elif action == "release":
            ev.legal_hold = False
            if ev.state == "LEGAL_HOLD":
                from ..evidence.models import evidence_transition
                evidence_transition(ev, "ADMISSIBLE", actor=user["uid"],
                                    reason="legal hold released")
        else:
            raise HTTPException(400, "action must be place or release")
        estore.save(ev)
        return evidence_json(ev)

    @app.post("/evidence/{evidence_id}/delete-decision")
    async def evidence_delete_decision(evidence_id: str, body: dict,
                                       user: dict = Depends(
                                           current_user)):
        require_permission(user, "document.delete")
        ev = load_evidence_or_404(evidence_id, user)
        used_by_active = bool(estore.contracts(tenant_id=user["tid"],
                                               case_id=ev.case_id))
        decision = evengine.delete(
            ev, hard=bool(body.get("hard")),
            ctx=RetentionContext(actor_role=user["role"],
                                 used_by_active_decision=used_by_active))
        estore.save(ev)
        return {"decision": decision.decision,
                "reasons": decision.reasons, "state": ev.state}

    @app.post("/evidence/{evidence_id}/human-verify-symbol")
    async def evidence_verify_symbol(evidence_id: str, body: dict,
                                     user: dict = Depends(current_user)):
        require_permission(user, "document.analyze")
        ev = load_evidence_or_404(evidence_id, user)
        if not str(body.get("purpose", "")).strip():
            raise HTTPException(400, "a narrow factual purpose is "
                                     "required")
        symbol = next((s for s in ev.symbols
                       if s.id == body.get("symbol_id")), None)
        if symbol is None:
            raise HTTPException(404, "symbol not found")
        mark_symbol_human_verified(symbol, purpose=body["purpose"],
                                   verified_by=user["uid"])
        estore.save(ev)
        return {"symbol_id": symbol.id, "trusted": symbol.trusted,
                "human_verified_for": symbol.human_verified_for}

    @app.get("/evidence/{evidence_id}/human-view")
    async def evidence_human_view(evidence_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        ev = load_evidence_or_404(evidence_id, user)
        if ev.sensitivity in ("sensitive", "legal"):
            require_permission(user, "document.view_sensitive")
        hv = human_view(ev)
        return {"view": "human", "evidence_id": hv.evidence_id,
                "original_filename": hv.original_filename,
                "original_reference": hv.original_reference,
                "state": hv.state, "sensitivity": hv.sensitivity,
                "can_open_original": hv.can_open_original,
                "untrusted_content_warning":
                    "stored content remains UNTRUSTED external data — "
                    "storage inside Finalis does not make it safe"}

    @app.get("/evidence/{evidence_id}/agent-view")
    async def evidence_agent_view(evidence_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        ev = load_evidence_or_404(evidence_id, user)
        # Symbols are refreshed FROM THE DATABASE: a reread never
        # upgrades trust (sticky untrusted markers).
        stored = estore.load_symbols(evidence_id, tenant_id=user["tid"])
        if stored:
            ev.symbols = stored
        av = agent_view(ev)
        return {"view": "agent", "evidence_id": av.evidence_id,
                "evidence_type": av.evidence_type, "state": av.state,
                "metadata": av.metadata,
                "symbols": [{"id": s.id, "kind": s.kind,
                             "trusted": s.trusted,
                             "human_verified_for": s.human_verified_for,
                             "origin": s.marker.origin}
                            for s in av.symbols],
                "safe_derivative_text": av.safe_derivative_text,
                "confidence": round(av.confidence, 4),
                "untrusted": av.untrusted,
                "note": "agent view carries facts and symbols only — "
                        "raw untrusted text is structurally absent"}

    @app.post("/evidence/{evidence_id}/ai-access-decision")
    async def evidence_ai_access(evidence_id: str,
                                 body: Optional[dict] = None,
                                 user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        body = body or {}
        ev = load_evidence_or_404(evidence_id, user)
        decision = evengine.ai_access(
            ev, tenant_id=user["tid"],
            actor_id=body.get("actor_id", "ai-worker"),
            purpose=body.get("purpose", "fact_extraction"),
            task_scoped_authorization=bool(
                body.get("task_scoped_authorization")),
            requested_raw=bool(body.get("requested_raw")))
        event = evengine.access_events[-1]
        estore.save_access_event(event)
        return {"decision": decision.decision,
                "reasons": decision.reasons,
                "allowed_view": decision.decision,
                "task_scope": body.get("purpose", "fact_extraction"),
                "access_event_id": event.id,
                "raw_content_included": False}

    @app.post("/evidence/requirement-check")
    async def evidence_requirement_check(body: dict,
                                         user: dict = Depends(
                                             current_user)):
        require_permission(user, "case.read")
        decision_type = body.get("decision_type", "")
        evidence = [evengine.objects[i]
                    for i in body.get("evidence_ids", [])
                    if i in evengine.objects
                    and evengine.objects[i].tenant_id == user["tid"]]
        check = check_requirements(
            decision_type, evidence,
            human_verified=bool(body.get("human_verified")))
        return {"decision_type": decision_type,
                "allowed": check.ok, "missing": check.missing,
                "reasons": check.reasons,
                "admissible": [e.id for e in evidence
                               if e.usable_for_decisions]}

    def _contract_hash(*, tenant_id: str, case_id: str, decision_type: str,
                       evidence_ids: list, facts: dict, hard_blockers: list,
                       causal_result: str, policy_version: str,
                       created_at: str) -> str:
        import hashlib as _h
        body = json.dumps({
            "t": tenant_id, "c": case_id, "d": decision_type,
            "e": sorted(evidence_ids), "f": facts,
            "hb": sorted(hard_blockers), "cr": causal_result,
            "pv": policy_version, "at": created_at}, sort_keys=True,
            default=str)
        return _h.sha256(body.encode()).hexdigest()

    def _evaluate_contract(*, tenant_id: str, actor: str, decision_type: str,
                           case_id: str, evidence_ids: list, facts: dict,
                           human_verified: bool, user_intent_reference,
                           untrusted_flag: bool,
                           would_survive: bool) -> dict:
        evidence = [evengine.objects[i] for i in evidence_ids
                    if i in evengine.objects]
        contract = evengine.build_contract(
            decision_type=decision_type, tenant_id=tenant_id,
            case_id=case_id, actor=actor, evidence=evidence,
            facts=facts, human_verified=human_verified)
        causal = causality_check(
            action_type=decision_type,
            user_intent_reference=user_intent_reference,
            untrusted_instruction_detected=untrusted_flag
            or any(e.injection_risk
                   > evengine.thresholds.max_injection_for_raw_ai
                   for e in evidence),
            would_action_survive_without_untrusted_text=would_survive)
        if contract.final_decision == "BLOCKED" \
                or causal.decision == "BLOCK":
            final = "BLOCKED"
        elif causal.decision == "HUMAN_REVIEW" \
                or contract.final_decision == "REVIEW":
            final = "HUMAN_REVIEW"
        else:
            final = "ALLOWED"
        contract.final_decision = ("ALLOWED" if final == "ALLOWED"
                                   else ("REVIEW" if final == "HUMAN_REVIEW"
                                         else "BLOCKED"))
        return {"contract": contract, "causal": causal, "final": final}

    @app.post("/evidence/decision-contract/validate")
    async def evidence_decision_contract(body: dict,
                                         user: dict = Depends(
                                             current_user)):
        """Requirement profiles + Causal Action Guard in one verdict:
        user intent + admissible facts decide — documents never do."""
        require_permission(user, "case.read")
        decision_type = body.get("decision_type", "")
        case_id = body.get("case_id", "")
        evidence_ids = body.get("evidence_ids", [])
        facts = body.get("facts") or {}
        intent = body.get("user_intent_reference")
        untrusted_flag = bool(body.get("untrusted_instruction_detected"))
        would_survive = bool(
            body.get("would_action_survive_without_untrusted_text", True))
        r = _evaluate_contract(
            tenant_id=user["tid"], actor=user["uid"],
            decision_type=decision_type, case_id=case_id,
            evidence_ids=evidence_ids, facts=facts,
            human_verified=bool(body.get("human_verified")),
            user_intent_reference=intent, untrusted_flag=untrusted_flag,
            would_survive=would_survive)
        contract, causal, final = r["contract"], r["causal"], r["final"]
        created_at = utcnow()
        pv = current_policy_version()
        chash = _contract_hash(
            tenant_id=user["tid"], case_id=case_id,
            decision_type=decision_type, evidence_ids=evidence_ids,
            facts=facts, hard_blockers=contract.hard_blockers,
            causal_result=causal.decision, policy_version=pv,
            created_at=created_at)
        estore.save_contract(
            contract, contract_hash=chash, policy_version=pv,
            requested_action=decision_type, causal_result=causal.decision,
            user_intent_reference=intent, would_survive=would_survive)
        return {"final": final, "contract_id": contract.id,
                "contract_hash": chash, "policy_version": pv,
                "admissible": contract.admissible_ids,
                "rejected": contract.rejected_ids,
                "hard_blockers": contract.hard_blockers,
                "causality": {"decision": causal.decision,
                              "reasons": causal.reasons},
                "case_completed_by_this": False}

    def _contract_json(row: dict) -> dict:
        return {"id": row["id"], "case_id": row["case_id"],
                "decision_type": row["decision_type"],
                "requested_action": row["requested_action"],
                "final_decision": row["final_decision"],
                "evidence_ids": json.loads(row["evidence_ids_json"]),
                "admissible": json.loads(row["admissible_json"]),
                "rejected": json.loads(row["rejected_json"]),
                "hard_blockers": json.loads(row["hard_blockers_json"]),
                "causal_result": row["causal_result"],
                "user_intent_reference": row["user_intent_reference"],
                "contract_hash": row["contract_hash"],
                "policy_version": row["policy_version"],
                "created_at": row["created_at"]}

    @app.get("/evidence/contracts/{contract_id}")
    async def evidence_contract_detail(contract_id: str,
                                       user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        row = estore.get_contract(contract_id, tenant_id=user["tid"])
        if row is None:
            raise HTTPException(404, "contract not found")
        drift = EvidencePolicyDriftReport.compare(row["policy_version"])
        return {**_contract_json(row),
                "policy_drift": {"drift": drift.drift,
                                 "detail": drift.detail,
                                 "current_version": drift.current_version}}

    @app.get("/evidence/{evidence_id}/contracts")
    async def evidence_contracts_by_evidence(evidence_id: str,
                                             user: dict = Depends(
                                                 current_user)):
        require_permission(user, "audit.view")
        load_evidence_or_404(evidence_id, user)
        return [_contract_json(r) for r in estore.contracts(
            tenant_id=user["tid"], evidence_id=evidence_id)]

    @app.get("/cases/{case_id}/evidence-contracts")
    async def case_evidence_contracts(case_id: str,
                                      user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        load_case_or_404(case_id, user)
        return [_contract_json(r) for r in estore.contracts(
            tenant_id=user["tid"], case_id=case_id)]

    @app.post("/evidence/contracts/{contract_id}/replay")
    async def evidence_contract_replay(contract_id: str,
                                       user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        row = estore.get_contract(contract_id, tenant_id=user["tid"])
        if row is None:
            raise HTTPException(404, "contract not found")
        r = _evaluate_contract(
            tenant_id=user["tid"], actor=user["uid"],
            decision_type=row["decision_type"], case_id=row["case_id"],
            evidence_ids=json.loads(row["evidence_ids_json"]),
            facts=json.loads(row["facts_json"]),
            human_verified=bool(row["human_verified"]),
            user_intent_reference=row["user_intent_reference"],
            untrusted_flag=(row["causal_result"] or "").startswith("BLOCK")
            or False,
            would_survive=bool(row["would_survive"])
            if row["would_survive"] is not None else True)
        drift = EvidencePolicyDriftReport.compare(row["policy_version"])
        return {"contract_id": contract_id,
                "stored_decision": row["final_decision"],
                "replayed_decision": r["final"],
                "same_decision": row["final_decision"] == r["final"],
                "policy_drift": drift.drift,
                "policy_detail": drift.detail,
                "stored_policy_version": row["policy_version"],
                "current_policy_version": drift.current_version}

    # -- V-E: derivatives -----------------------------------------------------------
    @app.get("/evidence/{evidence_id}/derivatives")
    async def evidence_derivatives_list(evidence_id: str,
                                        user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        load_evidence_or_404(evidence_id, user)
        return estore.derivatives(evidence_id, tenant_id=user["tid"])

    @app.post("/evidence/{evidence_id}/derivatives/generate")
    async def evidence_derivative_generate(evidence_id: str,
                                           user: dict = Depends(
                                               current_user)):
        require_permission(user, "document.analyze")
        ev = load_evidence_or_404(evidence_id, user)
        from ..evidence.gates import admissibility_gate as _adm
        blockers = _adm(ev, tenant_id=user["tid"]).hard_blockers
        manifest = generate_manifest(ev, now_iso=utcnow(),
                                     has_hard_blocker=bool(blockers))
        estore.save_derivative(user["tid"], manifest)
        return {"id": manifest.id,
                "derivative_kind": manifest.derivative_kind,
                "policy_decision": manifest.policy_decision,
                "confidence": manifest.confidence,
                "is_placeholder": manifest.is_placeholder,
                "safe_derivative_score": manifest.confidence,
                "safe_text": manifest.safe_text,
                "limitations": manifest.limitations,
                "manifest_hash": manifest.manifest_hash,
                "raw_content_included": False}

    # -- V-E: WORM / retention immutability -----------------------------------------
    @app.get("/evidence/{evidence_id}/immutability")
    async def evidence_immutability(evidence_id: str,
                                    user: dict = Depends(current_user)):
        require_permission(user, "document.view")
        load_evidence_or_404(evidence_id, user)
        cap = storage_worm_capability(evengine.storage.name)
        pol = estore.retention_policy(evidence_id, tenant_id=user["tid"])
        return {"native_worm": cap.native_worm,
                "simulated_modes": cap.simulated_modes,
                "note": cap.note,
                "retention_policy": pol}

    @app.post("/evidence/{evidence_id}/retention-policy")
    async def evidence_set_retention(evidence_id: str, body: dict,
                                     user: dict = Depends(current_user)):
        require_permission(user, "override.compliance_review")
        ev = load_evidence_or_404(evidence_id, user)
        try:
            pol = RetentionPolicy(
                tenant_id=user["tid"], evidence_id=evidence_id,
                mode=body.get("mode", "SIMULATED_GOVERNANCE"),
                retention_until=datetime.fromisoformat(body["retention_until"])
                if body.get("retention_until") else None)
        except ValueError as e:
            raise HTTPException(400, str(e))
        estore.save_retention_policy(pol)
        return {"mode": pol.mode, "native_worm": pol.native_worm,
                "label": pol.label,
                "retention_until": pol.retention_until.isoformat()
                if pol.retention_until else None}

    # -- V-E: Merkle transparency ledger --------------------------------------------
    def _leaf_for(cr: dict) -> str:
        import hashlib as _h
        payload_hash = _h.sha256(cr["payload_json"].encode()).hexdigest()
        return _mrk.leaf_hash(
            tenant_id=cr["tenant_id"], evidence_id=cr["evidence_id"],
            event_id=cr["id"], event_type=cr["event_type"],
            event_timestamp=cr["created_at"],
            previous_event_hash=cr["hash_prev"],
            event_payload_hash=payload_hash)

    @app.post("/evidence/merkle-roots/generate")
    async def evidence_merkle_generate(user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        events = estore.all_chain_events(tenant_id=user["tid"])
        leaves = [_leaf_for(cr) for cr in events]
        root = _mrk.EvidenceMerkleRoot(
            tenant_id=user["tid"], root=_mrk.merkle_root(leaves),
            size=len(leaves))
        prior = estore.merkle_roots(tenant_id=user["tid"])
        consistent = True
        if prior:
            old_leaves = json.loads(prior[-1]["leaves_json"])
            consistent = _mrk.consistency_proof_ok(old_leaves, leaves)
        estore.save_merkle_root(root, leaves, created_at=utcnow())
        return {"batch_id": root.batch_id, "root": root.root,
                "size": root.size, "consistent_with_prior": consistent,
                "external_anchoring": "NONE — local ledger only "
                                      "(no blockchain/timestamping)"}

    @app.get("/evidence/{evidence_id}/merkle-proof")
    async def evidence_merkle_proof(evidence_id: str,
                                    event_id: Optional[str] = None,
                                    user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        load_evidence_or_404(evidence_id, user)
        events = estore.all_chain_events(tenant_id=user["tid"])
        leaves = [_leaf_for(cr) for cr in events]
        # Prove the first chain event of this evidence (or a named one).
        target_idx = next(
            (i for i, cr in enumerate(events)
             if cr["evidence_id"] == evidence_id
             and (event_id is None or cr["id"] == event_id)), None)
        if target_idx is None:
            raise HTTPException(404, "chain event not found")
        proof = _mrk.build_proof(leaves, target_idx)
        return {"evidence_id": evidence_id,
                "leaf_hash": proof.leaf_hash, "root": proof.root,
                "path": [[h, r] for h, r in proof.path],
                "index": proof.index, "size": proof.size,
                "verifies": _mrk.verify_proof(proof)}

    @app.post("/evidence/merkle-roots/{root_id}/verify")
    async def evidence_merkle_verify(root_id: str,
                                     user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        row = estore.get_merkle_root(root_id, tenant_id=user["tid"])
        if row is None:
            raise HTTPException(404, "root not found")
        stored_leaves = json.loads(row["leaves_json"])
        # Recompute leaves from the live chain and compare the root.
        events = estore.all_chain_events(tenant_id=user["tid"])
        current_leaves = [_leaf_for(cr) for cr in events]
        recomputed = _mrk.merkle_root(stored_leaves)
        tampered = recomputed != row["root"]
        return {"batch_id": root_id, "stored_root": row["root"],
                "recomputed_root": recomputed,
                "root_intact": not tampered,
                "chain_still_matches_root":
                    _mrk.merkle_root(current_leaves[:len(stored_leaves)])
                    == row["root"] if len(current_leaves) >= len(
                        stored_leaves) else False}

    # -- Transparency Log Core: server-verified consistency proofs -----------------
    def _checkpoint(row: dict) -> dict:
        """Honest checkpoint metadata. Signatures / witness cosignatures /
        SCITT receipts are future-ready slots only — none are implemented,
        no external transparency service is called."""
        import hashlib as _h
        cp = _h.sha256(
            f"FINALIS_EVIDENCE_CHECKPOINT_V1|{row['tenant_id']}|"
            f"{row['root']}|{row['size']}|sha256".encode()).hexdigest()
        return {"checkpoint_hash": cp, "checkpoint_algorithm": "sha256",
                "checkpoint_created_at": row["created_at"],
                "checkpoint_signature_status": "NOT_IMPLEMENTED",
                "witness_cosignature_status": "NOT_IMPLEMENTED",
                "scitt_receipt_status": "NOT_IMPLEMENTED"}

    _CONSISTENCY_NOTES = [
        "Finalis server-verified append-only consistency.",
        "Merkle consistency proves append-only tree evolution only; it does "
        "not prove legal validity.",
        "Checkpoint signatures are not implemented.",
        "Witness cosignatures are not implemented.",
        "SCITT receipts are not implemented.",
        "No external transparency service is called.",
    ]

    @app.get("/evidence/merkle-roots/{current_root_id}/consistency")
    async def evidence_merkle_consistency(
            current_root_id: str, previous_root_id: Optional[str] = None,
            user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        if not previous_root_id:
            raise HTTPException(400, "previous_root_id is required")

        def _shell(status: str, reason: str, cur=None, prev=None):
            return {"previous_root_id": previous_root_id,
                    "current_root_id": current_root_id,
                    "previous_tree_size": prev["size"] if prev else None,
                    "current_tree_size": cur["size"] if cur else None,
                    "previous_root_hash": prev["root"] if prev else None,
                    "current_root_hash": cur["root"] if cur else None,
                    "consistency_proof_nodes": [], "algorithm": "sha256",
                    "status": status, "append_only_verified": False,
                    "reason": reason, "verified_at": utcnow(),
                    "checkpoint": _checkpoint(cur) if cur else None,
                    "notes": _CONSISTENCY_NOTES}

        # Tenant-scoped lookups: a cross-tenant root id simply isn't found —
        # roots are never compared across tenants.
        cur = estore.get_merkle_root(current_root_id, tenant_id=user["tid"])
        prev = estore.get_merkle_root(previous_root_id, tenant_id=user["tid"])
        if cur is None or prev is None:
            return _shell("ROOT_NOT_FOUND",
                          "A referenced root was not found for this tenant "
                          "(cross-tenant consistency checks are not allowed).",
                          cur, prev)
        report = _mrk.consistency_report(
            old_leaves=json.loads(prev["leaves_json"]),
            old_root=prev["root"], old_size=prev["size"],
            new_leaves=json.loads(cur["leaves_json"]),
            new_root=cur["root"], new_size=cur["size"], algorithm="sha256")
        return {"previous_root_id": previous_root_id,
                "current_root_id": current_root_id,
                "previous_tree_size": prev["size"],
                "current_tree_size": cur["size"],
                "previous_root_hash": prev["root"],
                "current_root_hash": cur["root"],
                "previous_tree_hash": report.previous_tree_hash,
                "current_tree_hash": report.current_tree_hash,
                "consistency_proof_nodes": report.proof_nodes,
                "algorithm": "sha256", "status": report.status,
                "append_only_verified": report.append_only_verified,
                "reason": report.reason, "verified_at": utcnow(),
                "checkpoint": _checkpoint(cur), "notes": _CONSISTENCY_NOTES}

    @app.get("/evidence/merkle-roots/{root_id}/lineage")
    async def evidence_merkle_lineage(root_id: str,
                                      user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        row = estore.get_merkle_root(root_id, tenant_id=user["tid"])
        if row is None:
            raise HTTPException(404, "root not found")
        roots = estore.merkle_roots(tenant_id=user["tid"])   # created_at order
        lineage, prev_id = [], None
        for r in roots:
            lineage.append({"root_id": r["id"], "tree_size": r["size"],
                            "root_hash": r["root"],
                            "previous_root_id": prev_id,
                            "created_at": r["created_at"]})
            prev_id = r["id"]
            if r["id"] == root_id:
                break
        return {"root_id": root_id, "algorithm": "sha256",
                "chain_length": len(lineage), "lineage": lineage,
                "checkpoint": _checkpoint(row), "notes": _CONSISTENCY_NOTES}

    # -- Canonical Evidence Report Package (EVIDENCE-REPORT-C2) ---------------------
    def _gather_evidence_signals(ev, user: dict) -> dict:
        """Assemble the server-side proof signals a report captures. Reuses
        the same tested Evidence data (integrity, Merkle inclusion, server-
        verified consistency, derivatives, contracts) — no faked values."""
        j = evidence_json(ev)
        events = estore.all_chain_events(tenant_id=user["tid"])
        leaves = [_leaf_for(cr) for cr in events]
        inclusion = {"status": "NOT_EXPOSED"}
        idx = next((i for i, cr in enumerate(events)
                    if cr["evidence_id"] == ev.id), None)
        if idx is not None and leaves:
            pr = _mrk.build_proof(leaves, idx)
            inclusion = {"status": "VERIFIED" if _mrk.verify_proof(pr)
                         else "NOT_VERIFIED", "root_id": None,
                         "root_hash": pr.root, "tree_size": pr.size,
                         "leaf_index": pr.index, "leaf_hash": pr.leaf_hash}
        consistency = {"status": "NOT_EXPOSED"}
        roots = estore.merkle_roots(tenant_id=user["tid"])
        if len(roots) >= 2:
            prev, cur = roots[-2], roots[-1]
            rep = _mrk.consistency_report(
                old_leaves=json.loads(prev["leaves_json"]),
                old_root=prev["root"], old_size=prev["size"],
                new_leaves=json.loads(cur["leaves_json"]),
                new_root=cur["root"], new_size=cur["size"])
            consistency = {"status": rep.status,
                           "append_only_verified": rep.append_only_verified,
                           "previous_root_id": prev["id"],
                           "current_root_id": cur["id"],
                           "proof_nodes": rep.proof_nodes}
        derivatives = [
            {"id": d.get("id"),
             "parent_evidence_id": d.get("parent_evidence_id", ev.id),
             "orphan": bool(d.get("parent_evidence_id")
                            and d.get("parent_evidence_id") != ev.id)}
            for d in estore.derivatives(ev.id, tenant_id=user["tid"])]
        contracts = [{"id": c["id"], "final_decision": c["final_decision"]}
                     for c in estore.contracts(tenant_id=user["tid"],
                                               evidence_id=ev.id)]
        integ = j.get("integrity") or {}
        ca = getattr(ev, "created_at", None)
        src = getattr(ev, "source_type", None) or getattr(ev, "source", None)
        return {"evidence": {
                    "id": ev.id, "case_id": ev.case_id,
                    "evidence_type": ev.evidence_type,
                    "source": str(src) if src is not None else "upload",
                    "created_at": ca.isoformat()
                    if hasattr(ca, "isoformat") else ca,
                    "content_hash": integ.get("sha256"),
                    "algorithm": integ.get("algorithm"),
                    "integrity_valid": integ.get("valid"),
                    "state": ev.state, "human_verified": ev.human_verified},
                "inclusion": inclusion, "consistency": consistency,
                "derivatives": derivatives, "contracts": contracts}

    @app.post("/evidence/{evidence_id}/proof-reports")
    async def create_proof_report(evidence_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        ev = load_evidence_or_404(evidence_id, user)
        signals = _gather_evidence_signals(ev, user)
        rid = str(uuid.uuid4())
        parent = estore.reports_for_evidence(evidence_id, tenant_id=user["tid"])
        payload = _rpt.build_report_payload(
            report_id=rid, tenant_id=user["tid"], generated_by=user["uid"],
            generated_at=utcnow(), signals=signals,
            supersedes_report_id=parent[-1]["id"] if parent else None)
        package = _rpt.build_package(payload)
        estore.save_report(
            report_id=rid, tenant_id=user["tid"], evidence_id=evidence_id,
            case_id=ev.case_id, report_type=_rpt.REPORT_TYPE,
            report_version=_rpt.REPORT_VERSION, report_status="GENERATED",
            report_hash=payload["report_metadata"]["report_hash"],
            package_hash=package["package_hash"],
            final_verdict=payload["report_metadata"]["final_verdict"],
            payload_json=json.dumps(payload),
            package_json=json.dumps(package), parent_report_id=None,
            supersedes_report_id=parent[-1]["id"] if parent else None,
            generated_by=user["uid"], created_at=utcnow())
        audit.append(event_type="EVIDENCE_PROOF_REPORT_GENERATED",
                     actor=user["uid"],
                     payload={"report_id": rid, "evidence_id": evidence_id,
                              "report_hash": payload["report_metadata"][
                                  "report_hash"]})
        return {"report_id": rid, "package": package, **payload}

    def _load_report_or_404(report_id: str, user: dict) -> dict:
        row = estore.get_report(report_id, tenant_id=user["tid"])
        if row is None:                          # incl. cross-tenant
            raise HTTPException(404, "proof report not found")
        return row

    @app.get("/evidence/proof-reports/{report_id}")
    async def get_proof_report(report_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        row = _load_report_or_404(report_id, user)
        payload = json.loads(row["payload_json"])
        return {"report_id": report_id, "package": json.loads(
            row["package_json"]), **payload}

    @app.get("/evidence/proof-reports/{report_id}/safe")
    async def get_proof_report_safe(report_id: str,
                                    user: dict = Depends(current_user)):
        # Safe/redacted view available to document.view roles (no audit.view
        # needed) — omits restricted fields, never changes stored truth.
        require_permission(user, "document.view")
        row = _load_report_or_404(report_id, user)
        return _rpt.safe_view(json.loads(row["payload_json"]))

    @app.post("/evidence/proof-reports/{report_id}/verify")
    async def verify_proof_report(report_id: str,
                                  user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        row = _load_report_or_404(report_id, user)
        result = _rpt.verify_report_artifact(
            json.loads(row["payload_json"]), row["report_hash"],
            row["package_hash"])
        return {"report_id": report_id, **result, "verified_at": utcnow()}

    @app.get("/evidence/{evidence_id}/proof-reports")
    async def list_proof_reports(evidence_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        load_evidence_or_404(evidence_id, user)
        return [{"report_id": r["id"], "report_hash": r["report_hash"],
                 "package_hash": r["package_hash"],
                 "final_verdict": r["final_verdict"],
                 "report_status": r["report_status"],
                 "created_at": r["created_at"],
                 "supersedes_report_id": r["supersedes_report_id"]}
                for r in estore.reports_for_evidence(
                    evidence_id, tenant_id=user["tid"])]

    @app.get("/evidence/proof-reports/{report_id}/diff")
    async def diff_proof_reports(report_id: str, other_report_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "audit.view")
        a = _load_report_or_404(report_id, user)
        b = _load_report_or_404(other_report_id, user)
        pa, pb = json.loads(a["payload_json"]), json.loads(b["payload_json"])

        def _flat(obj, prefix=""):
            out = {}
            if isinstance(obj, dict):
                for k, v in obj.items():
                    out.update(_flat(v, f"{prefix}.{k}" if prefix else k))
            elif isinstance(obj, list):
                out[prefix] = _rpt.canonical_json(obj)
            else:
                out[prefix] = obj
            return out
        VOL = tuple(_rpt.EXCLUDED_HASH_FIELDS)
        fa, fb = _flat(pa), _flat(pb)
        changed = []
        for k in sorted(set(fa) | set(fb)):
            if any(k.endswith(v) for v in VOL):
                continue                         # ignore volatile fields
            if fa.get(k) != fb.get(k):
                changed.append({"field": k, "a": fa.get(k), "b": fb.get(k)})
        return {"report_id": report_id, "other_report_id": other_report_id,
                "report_hash_a": a["report_hash"],
                "report_hash_b": b["report_hash"],
                "identical_proof_state": a["report_hash"] == b["report_hash"],
                "changed_fields": changed,
                "note": "Volatile fields (ids, timestamps, hashes, signature) "
                        "are excluded from the diff."}

    # ---- Relationship Core (CRM-B: persistence + API over CRM-A) --------------
    from ..crm.adapters import NullCrmAdapter, default_policy, \
        idempotency_key as make_idempotency_key
    from ..crm.dedupe import duplicate_candidate, merge_parties
    from ..crm.engine import RelationshipEngine
    from ..crm.graph import CrossTenantLinkError
    from ..crm.models import (ConsentRecord, ContactPoint,
                              CustomerMemoryItem, CustomerPromise,
                              ExternalCrmReference, ExternalFieldMapping,
                              OrganizationProfile, Party, PersonProfile)
    from ..crm.sync import SyncRequest, record_sync_event, sync_decision
    from .crm_store import CrmStore

    crm = RelationshipEngine(audit)
    crm_store = CrmStore(db)
    crm_store.hydrate(crm)               # DB is the source of truth
    crm_adapter = NullCrmAdapter()       # SCAFFOLDED_ONLY — talks to nothing
    app.state.crm, app.state.crm_store = crm, crm_store

    # RBAC mapping (existing catalog, disclosed): reads -> case.read;
    # writes -> case.update; memory verification -> action.approve;
    # merge -> tenant.manage_users; external refs/sync -> tenant.
    # manage_integrations. AI workers hold none of the human-judgment
    # permissions, and the engine additionally refuses non-human actors.
    def load_crm_party_or_404(party_id: str, user: dict) -> Party:
        p = crm.graph.parties.get(party_id)
        if p is None or p.tenant_id != user["tid"]:
            raise HTTPException(404, "party not found")
        return p

    def crm_party_json(p: Party) -> dict:
        return {"id": p.id, "kind": p.kind,
                "display_name": p.display_name,
                "roles": sorted(p.roles),
                "contact_points": [{"id": c.id, "kind": c.kind,
                                    "value": c.value,
                                    "preferred": c.preferred}
                                   for c in p.contact_points],
                "merged_into_id": p.merged_into_id}

    @app.get("/crm/parties")
    async def crm_list_parties(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        rows = crm_store.list_parties(tenant_id=user["tid"])
        # Bridge: legacy case-contact parties, read-only, labeled.
        legacy = [{"id": r["id"], "kind": "person",
                   "display_name": r["display_name"],
                   "legacy_case_contact": True}
                  for r in db.all("SELECT id, display_name FROM parties "
                                  "WHERE tenant_id=?", user["tid"])]
        return {"parties": rows, "legacy_case_contacts": legacy}

    @app.post("/crm/parties")
    async def crm_create_party(body: dict,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        if not str(body.get("display_name", "")).strip():
            raise HTTPException(400, "display_name required")
        try:
            p = Party(
                tenant_id=user["tid"],
                kind=body.get("kind", "person"),
                display_name=body["display_name"],
                person=PersonProfile(**body["person"])
                if body.get("person") else None,
                organization=OrganizationProfile(**body["organization"])
                if body.get("organization") else None,
                roles=set(body.get("roles", ["customer"])))
            for cp in body.get("contact_points", []):
                p.contact_points.append(ContactPoint(
                    kind=cp["kind"], value=cp["value"],
                    label=cp.get("label", "")))
        except (ValueError, KeyError, TypeError) as e:
            raise HTTPException(400, f"invalid party payload: {e}")
        crm.graph.add_party(p)
        crm_store.save_party(p)
        audit.append(event_type="CRM_PARTY_CREATED", actor=user["uid"],
                     payload={"party_id": p.id, "kind": p.kind})
        return crm_party_json(p)

    @app.get("/crm/parties/{party_id}")
    async def crm_party_detail(party_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = load_crm_party_or_404(party_id, user)
        return {**crm_party_json(p),
                "cases": crm.graph.cases_of(p.id, tenant_id=user["tid"]),
                "open_promises": [
                    {"promisor": x.promisor, "what": x.what,
                     "status": x.status}
                    for x in crm.open_promises(p.id,
                                               tenant_id=user["tid"])]}

    @app.patch("/crm/parties/{party_id}")
    async def crm_update_party(party_id: str, body: dict,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        p = load_crm_party_or_404(party_id, user)
        if "display_name" in body:
            if not str(body["display_name"]).strip():
                raise HTTPException(400, "display_name cannot be empty")
            p.display_name = body["display_name"]
        if "roles" in body:
            try:
                p.roles = set(body["roles"])
                p.__post_init__()
            except ValueError as e:
                raise HTTPException(400, str(e))
        crm_store.save_party(p)
        return crm_party_json(p)

    @app.get("/crm/parties/{party_id}/contacts")
    async def crm_contacts(party_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return crm_party_json(load_crm_party_or_404(party_id, user)
                              )["contact_points"]

    @app.post("/crm/parties/{party_id}/contacts")
    async def crm_add_contact(party_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        p = load_crm_party_or_404(party_id, user)
        try:
            cp = ContactPoint(kind=body.get("kind", ""),
                              value=body.get("value", ""),
                              label=body.get("label", ""))
        except ValueError as e:
            raise HTTPException(400, str(e))
        p.contact_points.append(cp)
        crm_store.save_party(p)
        return {"id": cp.id, "kind": cp.kind, "value": cp.value}

    # -- consent -----------------------------------------------------------------
    @app.get("/crm/parties/{party_id}/consents")
    async def crm_consents(party_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_crm_party_or_404(party_id, user)
        return [{"channel": c.channel, "status": c.status,
                 "source": c.source}
                for c in crm.consents
                if c.party_id == party_id and c.tenant_id == user["tid"]]

    @app.post("/crm/parties/{party_id}/consents")
    async def crm_record_consent(party_id: str, body: dict,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        load_crm_party_or_404(party_id, user)
        try:
            record = ConsentRecord(
                tenant_id=user["tid"], party_id=party_id,
                channel=body.get("channel", ""),
                status=body.get("status", ""),
                source=body.get("source", "portal"),
                recorded_by=user["uid"])
        except ValueError as e:
            raise HTTPException(400, str(e))
        crm.record_consent(record)
        crm_store.save_consent(record)
        return {"channel": record.channel, "status": record.status}

    @app.post("/crm/consent/check")
    async def crm_consent_check(body: dict,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = load_crm_party_or_404(body.get("party_id", ""), user)
        d = crm.can_contact(p, channel=body.get("channel", "EMAIL"),
                            purpose=body.get("purpose", "service"))
        return {"allowed": d.allowed,
                "requires_review": d.requires_review,
                "reasons": d.reasons}

    # -- promises ------------------------------------------------------------------
    @app.get("/crm/parties/{party_id}/promises")
    async def crm_promises_list(party_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_crm_party_or_404(party_id, user)
        return [{"id": p.id, "promisor": p.promisor, "what": p.what,
                 "status": p.status, "case_id": p.case_id,
                 "due_at": p.due_at.isoformat() if p.due_at else None}
                for p in crm.promises
                if p.party_id == party_id and p.tenant_id == user["tid"]]

    @app.post("/crm/parties/{party_id}/promises")
    async def crm_add_promise(party_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        load_crm_party_or_404(party_id, user)
        due_at = None
        if body.get("due_at"):
            try:
                due_at = datetime.fromisoformat(body["due_at"])
            except ValueError:
                raise HTTPException(400, "invalid due_at")
        try:
            promise = crm.record_promise(CustomerPromise(
                tenant_id=user["tid"], party_id=party_id,
                promisor=body.get("promisor", ""),
                what=body.get("what", ""), due_at=due_at,
                case_id=body.get("case_id")))
        except ValueError as e:
            raise HTTPException(400, str(e))
        crm_store.save_promise(promise)
        return {"id": promise.id, "promisor": promise.promisor,
                "due_at": promise.due_at.isoformat()
                if promise.due_at else None}

    # -- memory --------------------------------------------------------------------
    @app.get("/crm/parties/{party_id}/memory")
    async def crm_memory_list(party_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_crm_party_or_404(party_id, user)
        items = crm.memory.for_party(party_id, tenant_id=user["tid"])
        out = []
        for m in items:
            if m.sensitive:
                d = rbac.access(actor_type="user",
                                actor_id=rbac_user_id(user),
                                tenant_id=user["tid"],
                                action="document.view_sensitive")
                if d.decision != "ALLOW":
                    continue                 # sensitive hidden safely
            out.append({"id": m.id, "memory_type": m.memory_type,
                        "content": m.content, "source": m.source,
                        "confidence": m.confidence,
                        "sensitive": m.sensitive})
        return out

    @app.post("/crm/parties/{party_id}/memory")
    async def crm_memory_add(party_id: str, body: dict,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        load_crm_party_or_404(party_id, user)
        try:
            item = crm.memory.add(CustomerMemoryItem(
                tenant_id=user["tid"], party_id=party_id,
                memory_type=body.get("memory_type", "SERVICE_HISTORY"),
                content=body.get("content") or {},
                source=body.get("source", "human"),
                confidence=float(body.get("confidence", 0.5)),
                sensitive=bool(body.get("sensitive"))))
        except ValueError as e:
            raise HTTPException(400, str(e))
        crm_store.save_memory(item)
        return {"id": item.id, "memory_type": item.memory_type}

    def _load_memory_or_404(memory_id: str, user: dict):
        item = next((m for m in crm.memory.items
                     if m.id == memory_id
                     and m.tenant_id == user["tid"]), None)
        if item is None:
            raise HTTPException(404, "memory item not found")
        return item

    @app.post("/crm/memory/{memory_id}/verify")
    async def crm_memory_verify(memory_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "action.approve")   # human judgment
        item = _load_memory_or_404(memory_id, user)
        crm.memory.verify(item, verified_by=user["uid"])
        crm_store.save_memory(item)
        return {"id": item.id, "memory_type": item.memory_type,
                "verified_by": item.verified_by}

    @app.post("/crm/memory/{memory_id}/dispute")
    async def crm_memory_dispute(memory_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        item = _load_memory_or_404(memory_id, user)
        crm.memory.dispute(item, by=user["uid"])
        crm_store.save_memory(item)
        return {"id": item.id, "memory_type": item.memory_type}

    @app.post("/crm/memory/{memory_id}/mark-stale")
    async def crm_memory_stale(memory_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        item = _load_memory_or_404(memory_id, user)
        item.memory_type = "STALE_FACT"
        crm_store.save_memory(item)
        return {"id": item.id, "memory_type": item.memory_type}

    # -- relationships / case links -----------------------------------------------
    @app.get("/crm/parties/{party_id}/relationships")
    async def crm_relationships(party_id: str,
                                user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_crm_party_or_404(party_id, user)
        return [{"to_id": e.to_id, "to_kind": e.to_kind, "role": e.role}
                for e in crm.graph.edges_of(party_id,
                                            tenant_id=user["tid"])]

    @app.post("/crm/relationships")
    async def crm_add_relationship(body: dict,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        try:
            if body.get("to_kind", "party") == "party":
                edge = crm.graph.link_parties(
                    tenant_id=user["tid"],
                    from_id=body.get("from_id", ""),
                    to_id=body.get("to_id", ""),
                    role=body.get("role", "member_of"))
            else:
                if body["to_kind"] == "case":
                    load_case_or_404(body.get("to_id", ""), user)
                edge = crm.graph.link(
                    tenant_id=user["tid"],
                    party_id=body.get("from_id", ""),
                    to_id=body.get("to_id", ""),
                    to_kind=body["to_kind"],
                    role=body.get("role", "customer"))
        except CrossTenantLinkError as e:
            raise HTTPException(404, str(e))
        except KeyError:
            raise HTTPException(400, "from_id, to_id, to_kind required")
        crm_store.save_edge(edge)
        return {"id": edge.id, "to_kind": edge.to_kind, "role": edge.role}

    @app.get("/crm/cases/{case_id}/parties")
    async def crm_case_parties(case_id: str,
                               user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_case_or_404(case_id, user)
        return [{"party_id": p.id, "display_name": p.display_name,
                 "role": role}
                for p, role in crm.graph.parties_of_case(
                    case_id, tenant_id=user["tid"])]

    # -- dedupe / merge -------------------------------------------------------------
    @app.get("/crm/parties/{party_id}/dedupe-candidates")
    async def crm_dedupe(party_id: str,
                         user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        target = load_crm_party_or_404(party_id, user)
        out = []
        for other_id, other in crm.graph.parties.items():
            if other_id == party_id or other.tenant_id != user["tid"] \
                    or other.merged_into_id:
                continue
            cand = duplicate_candidate(target, other)
            if cand.verdict != "NOT_DUPLICATE":
                out.append({"party_id": other_id, "score": cand.score,
                            "verdict": cand.verdict,
                            "signals": cand.signals})
        return out

    @app.post("/crm/merge")
    async def crm_merge(body: dict,
                        user: dict = Depends(current_user)):
        require_permission(user, "tenant.manage_users")
        surviving = load_crm_party_or_404(
            body.get("surviving_party_id", ""), user)
        merged = load_crm_party_or_404(
            body.get("merged_party_id", ""), user)
        if not str(body.get("reason", "")).strip():
            raise HTTPException(400, "merge requires a written reason")
        cand = duplicate_candidate(surviving, merged)
        try:
            decision = merge_parties(cand, surviving=surviving,
                                     merged=merged,
                                     decided_by=user["uid"],
                                     reason=body["reason"], audit=audit)
        except PermissionError as e:
            raise HTTPException(409, str(e))
        crm_store.save_party(merged)
        crm_store.save_merge_decision(decision)
        return {"surviving_party_id": decision.surviving_party_id,
                "merged_party_ids": decision.merged_party_ids,
                "reason": decision.reason}

    # -- external CRM references + sync decisions ------------------------------
    @app.get("/crm/parties/{party_id}/external-references")
    async def crm_ext_refs(party_id: str,
                           user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        load_crm_party_or_404(party_id, user)
        return crm_store.external_refs(party_id, tenant_id=user["tid"])

    @app.post("/crm/parties/{party_id}/external-references")
    async def crm_add_ext_ref(party_id: str, body: dict,
                              user: dict = Depends(current_user)):
        require_permission(user, "tenant.manage_integrations")
        load_crm_party_or_404(party_id, user)
        try:
            ref = ExternalCrmReference(
                tenant_id=user["tid"], party_id=party_id,
                provider=body.get("provider", ""),
                object_kind=body.get("object_kind", ""),
                external_id=body.get("external_id", ""))
        except ValueError as e:
            raise HTTPException(400, str(e))
        crm_store.save_external_ref(ref)
        return {"id": ref.id, "provider": ref.provider,
                "external_id": ref.external_id}

    def _sync_request(body: dict, user: dict,
                      direction: str) -> SyncRequest:
        return SyncRequest(
            tenant_id=user["tid"], policy_tenant_id=user["tid"],
            direction=direction, actor_id=user["uid"],
            actor_has_permission=True,
            field=body.get("field", ""),
            internal_value=body.get("internal_value"),
            internal_verified=bool(body.get("internal_verified")),
            internal_changed=bool(body.get("internal_changed")),
            external_value=body.get("external_value"),
            external_changed=bool(body.get("external_changed")),
            marketing_consent_denied=bool(
                body.get("marketing_consent_denied")),
            is_deletion=bool(body.get("is_deletion")))

    def _sync_policy(user: dict, body: dict):
        policy = default_policy(user["tid"])
        policy.enabled = bool(body.get("policy_enabled"))
        policy.dry_run = bool(body.get("policy_dry_run", True))
        policy.allow_export = bool(body.get("policy_allow_export"))
        policy.field_mappings = [ExternalFieldMapping(
            provider=policy.provider, canonical_field=f,
            external_field=f) for f in body.get("mapped_fields",
                                                ["email", "phone"])]
        return policy

    @app.post("/crm/sync/dry-run")
    async def crm_sync_dry_run(body: dict,
                               user: dict = Depends(current_user)):
        """Dry-run: decision + adapter dry-run push. NOTHING external is
        written (NullCrmAdapter is SCAFFOLDED_ONLY, talks to nothing)."""
        require_permission(user, "tenant.manage_integrations")
        direction = body.get("direction", "export")
        decision = sync_decision(_sync_request(body, user, direction),
                                 _sync_policy(user, body))
        key = make_idempotency_key(
            tenant_id=user["tid"], provider="null-crm",
            object_kind="Contact",
            external_id=body.get("external_id", "x"),
            operation=f"{direction}:{body.get('field', '')}")
        adapter_result = crm_adapter.push_object(
            tenant_id=user["tid"], object_kind="Contact",
            payload={body.get("field", ""): body.get("internal_value")},
            idempotency_key=key, dry_run=True)
        event = record_sync_event(
            tenant_id=user["tid"], provider="null-crm",
            direction="dry_run", object_kind="Contact",
            decision=decision,
            detail={"field": body.get("field", ""),
                    "note": body.get("note", "")},
            idempotency_key=key, audit=audit)
        crm_store.save_sync_event(event)
        return {"decision": decision.decision,
                "reasons": decision.reasons,
                "idempotency_key": key,
                "adapter": adapter_result,
                "external_write_happened": False}

    @app.post("/crm/sync/decision")
    async def crm_sync_decision_api(body: dict,
                                    user: dict = Depends(current_user)):
        require_permission(user, "tenant.manage_integrations")
        direction = body.get("direction", "import")
        decision = sync_decision(_sync_request(body, user, direction),
                                 _sync_policy(user, body))
        return {"decision": decision.decision,
                "reasons": decision.reasons,
                "conflict": decision.conflict.__dict__
                if decision.conflict else None}

    # ---- audit --------------------------------------------------------------------------------------
    @app.get("/audit/verify/{case_id}")
    async def audit_verify(case_id: str,
                           user: dict = Depends(current_user)):
        load_case_or_404(case_id, user)
        fresh = DbAuditLog(db)      # re-read from SQL and verify
        return {"chain_valid": fresh.verify_chain(),
                "events_total": len(fresh.events()),
                "events_case": len(fresh.events(case_id=case_id))}

    # ---- AI Employee identity + authority boundary (CORE-A1) --------------------------
    from ..ai_employee.authority import evaluate_ai_employee_authority
    from ..ai_employee.identity import (HONESTY_LABELS as AI_HONESTY,
                                        capability_snapshot, employee_json)
    from ..ai_employee.store import AIEmployeeStore
    ai_store = AIEmployeeStore(db)
    app.state.ai_store = ai_store

    def _load_ai_employee_or_404(ai_employee_id: str, user: dict):
        emp = ai_store.get(ai_employee_id, tenant_id=user["tid"])
        if emp is None:                         # incl. cross-tenant
            raise HTTPException(404, "AI employee not found")
        return emp

    @app.get("/ai-employees")
    async def list_ai_employees(user: dict = Depends(current_user)):
        require_permission(user, "tenant.view")
        emps = ai_store.list(tenant_id=user["tid"])
        if not emps:                            # lazily seed the tenant default
            emps = [ai_store.get_or_create_default(tenant_id=user["tid"],
                                                   created_by="system")]
        return [employee_json(e) for e in emps]

    @app.post("/ai-employees/default")
    async def create_default_ai_employee(user: dict = Depends(current_user)):
        # Creating/registering identity is an admin action, never an AI or
        # viewer action — an AI employee can never create/modify identity.
        require_permission(user, "tenant.manage_users")
        emp = ai_store.get_or_create_default(tenant_id=user["tid"],
                                             created_by=user["uid"])
        return employee_json(emp)

    @app.get("/ai-employees/{ai_employee_id}")
    async def get_ai_employee(ai_employee_id: str,
                              user: dict = Depends(current_user)):
        require_permission(user, "tenant.view")
        return employee_json(_load_ai_employee_or_404(ai_employee_id, user))

    @app.get("/ai-employees/{ai_employee_id}/authority")
    async def get_ai_employee_authority(ai_employee_id: str,
                                        user: dict = Depends(current_user)):
        require_permission(user, "tenant.view")
        emp = _load_ai_employee_or_404(ai_employee_id, user)
        prof = employee_json(emp)
        return {"ai_employee_id": emp.id,
                "read_only_action_types": prof["read_only_action_types"],
                "draft_only_action_types": prof["draft_only_action_types"],
                "approval_required_action_types":
                    prof["approval_required_action_types"],
                "forbidden_action_types": prof["forbidden_action_types"],
                "production_autonomy_enabled": False,
                "honesty_labels": AI_HONESTY}

    @app.get("/ai-employees/{ai_employee_id}/capability-snapshot")
    async def get_ai_capability_snapshot(ai_employee_id: str,
                                         user: dict = Depends(current_user)):
        require_permission(user, "tenant.view")
        return capability_snapshot(
            _load_ai_employee_or_404(ai_employee_id, user))

    @app.post("/ai-employees/{ai_employee_id}/authority/check")
    async def check_ai_employee_authority(ai_employee_id: str, body: dict,
                                          user: dict = Depends(current_user)):
        # Deterministic, side-effect-free pre-check. Task text / body cannot
        # change the decision — only action_type/segment/subject drive it.
        require_permission(user, "tenant.view")
        emp = _load_ai_employee_or_404(ai_employee_id, user)
        decision = evaluate_ai_employee_authority(
            employee=emp, action_type=str(body.get("action_type", "")),
            tenant_id=user["tid"], object_type=str(body.get("object_type", "")),
            object_id=str(body.get("object_id", "")),
            segment=str(body.get("segment", "")),
            subject_tenant_id=body.get("subject_tenant_id"))
        return {"ai_employee_id": emp.id, **decision.to_json()}

    # ---- Secure Work Intake Registry + Canonical Task Contract (CORE-A2) --------------
    from ..ai_employee import tasks as _tasks
    from ..ai_employee.task_store import AITaskStore
    task_store = AITaskStore(db)
    app.state.task_store = task_store

    _DECISION_TO_STATUS = {
        "BLOCKED": "BLOCKED", "APPROVAL_REQUIRED": "ACCEPTED",
        "ALLOWED_DRAFT_ONLY": "ACCEPTED", "READ_ONLY_ALLOWED": "ACCEPTED",
        "HUMAN_REVIEW": "NEEDS_CLARIFICATION", "NOT_IMPLEMENTED":
        "NOT_IMPLEMENTED"}

    def _build_task_response(row: dict) -> dict:
        return json.loads(row["payload_json"])

    @app.get("/ai-tasks/types")
    async def ai_task_types(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return {"task_types": {t: {"segment": m["segment"],
                                   "proposed_action": m["action"],
                                   "purpose_category": m["purpose_category"],
                                   "default_risk": m["risk"],
                                   "allowed_output_types": m["outputs"],
                                   "allowed_data_scopes": m["scopes"]}
                               for t, m in _tasks.TASK_TYPES.items()},
                "source_channels": sorted(_tasks.SOURCE_CHANNELS),
                "honesty_labels": _tasks.HONESTY_LABELS}

    @app.post("/ai-tasks")
    async def create_ai_task(body: dict, user: dict = Depends(current_user)):
        require_permission(user, "case.update")     # delegating work = write
        task_type = str(body.get("task_type", ""))
        if task_type not in _tasks.TASK_TYPES:
            raise HTTPException(400, f"unsupported task_type '{task_type}'")
        meta = _tasks.TASK_TYPES[task_type]

        # Assigned AI employee (tenant-scoped; default if unspecified).
        emp_id = body.get("assigned_ai_employee_id")
        emp = (ai_store.get(emp_id, tenant_id=user["tid"]) if emp_id
               else ai_store.get_or_create_default(tenant_id=user["tid"]))
        if emp is None:
            raise HTTPException(404, "assigned AI employee not found")
        snap = capability_snapshot(emp)

        title = str(body.get("task_title", ""))
        desc = str(body.get("task_description", ""))
        subject_type = body.get("subject_type")
        subject_id = body.get("subject_id")
        subject_tenant_id = body.get("subject_tenant_id")
        source_channel = str(body.get("source_channel", "WEB"))
        if source_channel not in _tasks.SOURCE_CHANNELS:
            raise HTTPException(400, "invalid source_channel")
        priority = str(body.get("priority", "NORMAL"))
        purpose = str(body.get("task_purpose")
                      or f"{task_type} for segment {meta['segment']}")

        # Untrusted-input detection (advisory; never changes the decision).
        flags = _tasks.detect_input_security_flags(title, desc)
        unsafe = _tasks.detect_unsafe_requested_actions(title, desc)
        risk_level, risk_reason = _tasks.classify_risk(task_type, unsafe)

        # CORE-A1 authority pre-check drives the decision — NOT the task text.
        decision = evaluate_ai_employee_authority(
            employee=emp, action_type=meta["action"], tenant_id=user["tid"],
            object_type=str(subject_type or ""),
            object_id=str(subject_id or ""), segment=meta["segment"],
            subject_tenant_id=subject_tenant_id)

        status = _DECISION_TO_STATUS.get(decision.decision, "NOT_IMPLEMENTED")
        clarification_qs: list = []
        # Missing required subject -> clarification.
        if task_type in _tasks.SUBJECT_REQUIRED and not subject_id \
                and status not in ("BLOCKED", "NOT_IMPLEMENTED"):
            status = "NEEDS_CLARIFICATION"
            clarification_qs = [f"Which {subject_type or 'subject'} is this "
                                f"{task_type} about? A subject reference is "
                                "required."]
        # Expiry at intake -> cannot be accepted.
        expires_at = body.get("expires_at")
        if expires_at and status not in ("BLOCKED", "NOT_IMPLEMENTED") \
                and str(expires_at) < utcnow():
            status = "EXPIRED"
        stale_after = body.get("stale_after")
        due_at = body.get("due_at")

        allowed_scopes, forbidden_scopes = _tasks.derive_data_scopes(task_type)
        requires_approval = decision.decision == "APPROVAL_REQUIRED"
        requires_consent = decision.required_consent_check
        requires_evidence = decision.required_evidence_check
        requires_tool_broker = decision.required_tool_broker
        requires_run_ledger = status == "ACCEPTED"

        envelope = _tasks.build_envelope(
            tenant_id=user["tid"], requester_user_id=user["uid"],
            assigned_ai_employee_id=emp.id, source_channel=source_channel,
            source_thread_ref=body.get("source_thread_ref"),
            source_message_ref=body.get("source_message_ref"),
            task_type=task_type, segment=meta["segment"],
            subject_type=subject_type, subject_id=subject_id, task_title=title,
            task_description=desc, priority=priority, due_at=due_at,
            expires_at=expires_at, task_purpose=purpose,
            purpose_category=meta["purpose_category"],
            authority_decision=decision.decision,
            authority_reason=decision.reason, risk_level=risk_level,
            requires_human_approval=requires_approval,
            requires_consent_check=requires_consent,
            requires_evidence_check=requires_evidence,
            requires_tool_broker=requires_tool_broker,
            forbidden_side_effects=_tasks.FORBIDDEN_SIDE_EFFECTS,
            input_security_flags=flags)
        env_hash = _tasks.envelope_hash(envelope)

        contract = _tasks.build_contract(
            tenant_id=user["tid"], requester_user_id=user["uid"],
            assigned_ai_employee_id=emp.id,
            capability_snapshot_hash=snap["capability_snapshot_hash"],
            task_type=task_type, segment=meta["segment"],
            subject_type=subject_type, subject_id=subject_id,
            task_purpose=purpose, purpose_category=meta["purpose_category"],
            allowed_data_scopes=allowed_scopes,
            forbidden_data_scopes=forbidden_scopes,
            allowed_output_types=meta["outputs"],
            forbidden_side_effects=_tasks.FORBIDDEN_SIDE_EFFECTS,
            authority_decision=decision.decision,
            authority_hard_fail=decision.hard_fail,
            requires_human_approval=requires_approval,
            requires_consent_check=requires_consent,
            requires_evidence_check=requires_evidence,
            requires_tool_broker=requires_tool_broker,
            requires_run_ledger=requires_run_ledger, risk_level=risk_level,
            risk_reason=risk_reason, expires_at=expires_at,
            stale_after=stale_after, clarification_required=bool(
                clarification_qs), clarification_questions=clarification_qs)
        con_hash = _tasks.contract_hash(contract)
        dedup_key = _tasks.deduplication_key(
            tenant_id=user["tid"], requester_user_id=user["uid"],
            source_channel=source_channel, task_type=task_type,
            subject_type=str(subject_type or ""),
            subject_id=str(subject_id or ""), task_title=title)

        idem = body.get("idempotency_key")
        if idem:
            prior = task_store.find_by_idempotency(
                tenant_id=user["tid"], requester_user_id=user["uid"],
                idempotency_key=str(idem))
            if prior is not None:
                if prior["envelope_hash"] == env_hash:
                    task_store.add_event(
                        task_id=prior["id"], tenant_id=user["tid"],
                        actor_id=user["uid"], actor_type="human",
                        event_type="IDEMPOTENCY_REPLAYED",
                        reason="same idempotency key + same envelope")
                    return {"idempotent_replay": True,
                            **_build_task_response(prior)}
                task_store.add_event(
                    task_id=prior["id"], tenant_id=user["tid"],
                    actor_id=user["uid"], actor_type="human",
                    event_type="IDEMPOTENCY_CONFLICT",
                    reason="same idempotency key + different envelope")
                raise HTTPException(409, "idempotency key reused with a "
                                    "different task envelope")

        task_id = str(uuid.uuid4())
        now = utcnow()
        payload = {
            "task_id": task_id, "tenant_id": user["tid"],
            "requester_user_id": user["uid"], "requester_role": user["role"],
            "assigned_ai_employee_id": emp.id,
            "assigned_ai_employee_capability_snapshot_hash":
                snap["capability_snapshot_hash"],
            "source_channel": source_channel,
            "source_channel_status": "ACTIVE" if source_channel in (
                "WEB", "API") else "NOT_IMPLEMENTED",
            "idempotency_key": idem, "deduplication_key": dedup_key,
            "canonical_task_envelope_hash": env_hash,
            "canonical_task_envelope_version": _tasks.ENVELOPE_VERSION,
            "canonical_task_contract_hash": con_hash,
            "canonical_task_contract_version": _tasks.CONTRACT_VERSION,
            "task_type": task_type, "task_title": title,
            "task_description": desc,
            "task_description_trust": "UNTRUSTED_USER_INPUT",
            "task_status": status, "task_version": 1,
            "segment": meta["segment"], "segment_confidence": 1.0,
            "segment_reason": f"task type '{task_type}' maps to segment",
            "priority": priority, "due_at": due_at, "expires_at": expires_at,
            "stale_after": stale_after, "created_at": now, "updated_at": now,
            "subject_type": subject_type, "subject_id": subject_id,
            "task_purpose": purpose,
            "purpose_category": meta["purpose_category"],
            "allowed_data_scopes": allowed_scopes,
            "forbidden_data_scopes": forbidden_scopes,
            "sensitive_data_flags": [],
            "authority_decision": decision.decision,
            "authority_reason": decision.reason,
            "authority_hard_fail": decision.hard_fail,
            "authority_snapshot_version": emp.profile_version,
            "risk_level": risk_level, "risk_reason": risk_reason,
            "requires_human_approval": requires_approval,
            "requires_consent_check": requires_consent,
            "requires_evidence_check": requires_evidence,
            "requires_tool_broker": requires_tool_broker,
            "requires_run_ledger": requires_run_ledger,
            "requires_clarification": bool(clarification_qs),
            "clarification_questions": clarification_qs,
            "clarification_reason": (clarification_qs[0] if clarification_qs
                                     else None),
            "allowed_output_types": meta["outputs"],
            "forbidden_side_effects": _tasks.FORBIDDEN_SIDE_EFFECTS,
            "unsafe_requested_actions": unsafe,
            "input_security_flags": flags,
            "draft_artifact_placeholder": None, "latest_result_summary": None,
            "canonical_task_envelope": envelope,
            "canonical_task_contract": contract,
            "honesty_labels": _tasks.HONESTY_LABELS,
        }
        try:
            task_store.save({
                "id": task_id, "tenant_id": user["tid"],
                "requester_user_id": user["uid"],
                "requester_role": user["role"],
                "assigned_ai_employee_id": emp.id,
                "capability_snapshot_hash": snap["capability_snapshot_hash"],
                "source_channel": source_channel, "idempotency_key": idem,
                "deduplication_key": dedup_key, "envelope_hash": env_hash,
                "contract_hash": con_hash, "task_type": task_type,
                "segment": meta["segment"], "task_status": status,
                "task_version": 1, "risk_level": risk_level,
                "authority_decision": decision.decision,
                "authority_hard_fail": int(decision.hard_fail),
                "subject_type": subject_type, "subject_id": subject_id,
                "expires_at": expires_at, "stale_after": stale_after,
                "payload_json": json.dumps(payload), "created_by": user["uid"],
                "created_at": now, "updated_at": now, "cancelled_at": None})
        except sqlite3.IntegrityError:
            # A concurrent worker won the idempotency race (UNIQUE index).
            # Resolve deterministically against the winner, never 500.
            winner = task_store.find_by_idempotency(
                tenant_id=user["tid"], requester_user_id=user["uid"],
                idempotency_key=str(idem)) if idem else None
            if winner is not None and winner["envelope_hash"] == env_hash:
                return {"idempotent_replay": True,
                        **_build_task_response(winner)}
            raise HTTPException(409, "idempotency key reused with a "
                                "different task envelope")

        # Append-only intake events (intake audit, NOT a run ledger).
        ev = lambda t, r="": task_store.add_event(  # noqa: E731
            task_id=task_id, tenant_id=user["tid"], actor_id=user["uid"],
            actor_type="human", event_type=t, reason=r)
        ev("TASK_CREATED")
        ev("CAPABILITY_SNAPSHOT_CAPTURED", snap["capability_snapshot_hash"])
        ev("AUTHORITY_CHECKED", decision.decision)
        ev("TASK_CONTRACT_CREATED", con_hash)
        ev("DATA_SCOPE_BOUNDARY_SET")
        if flags != ["NONE"]:
            ev("UNTRUSTED_INPUT_FLAGGED", ", ".join(flags))
        ev({"ACCEPTED": "TASK_ACCEPTED", "BLOCKED": "TASK_BLOCKED",
            "NEEDS_CLARIFICATION": "TASK_NEEDS_CLARIFICATION",
            "NOT_IMPLEMENTED": "TASK_NOT_IMPLEMENTED",
            "EXPIRED": "TASK_EXPIRED"}.get(status, "TASK_CREATED"),
           decision.reason)
        audit.append(event_type="AI_TASK_INTAKE", actor=user["uid"],
                     payload={"task_id": task_id, "task_type": task_type,
                              "status": status,
                              "authority_decision": decision.decision})
        return payload

    def _load_task_or_404(task_id: str, user: dict) -> dict:
        row = task_store.get(task_id, tenant_id=user["tid"])
        if row is None:                          # incl. cross-tenant
            raise HTTPException(404, "task not found")
        return row

    @app.get("/ai-tasks")
    async def list_ai_tasks(user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return [json.loads(r["payload_json"])
                for r in task_store.list(tenant_id=user["tid"])]

    @app.get("/ai-tasks/{task_id}")
    async def get_ai_task(task_id: str, user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        return _build_task_response(_load_task_or_404(task_id, user))

    @app.get("/ai-tasks/{task_id}/envelope")
    async def get_ai_task_envelope(task_id: str,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _build_task_response(_load_task_or_404(task_id, user))
        return {"canonical_task_envelope_hash":
                p["canonical_task_envelope_hash"],
                "canonical_task_envelope_version":
                p["canonical_task_envelope_version"],
                "canonical_task_envelope": p["canonical_task_envelope"]}

    @app.get("/ai-tasks/{task_id}/contract")
    async def get_ai_task_contract(task_id: str,
                                   user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        p = _build_task_response(_load_task_or_404(task_id, user))
        return {"canonical_task_contract_hash":
                p["canonical_task_contract_hash"],
                "canonical_task_contract_version":
                p["canonical_task_contract_version"],
                "canonical_task_contract": p["canonical_task_contract"]}

    @app.get("/ai-tasks/{task_id}/intake-events")
    async def get_ai_task_events(task_id: str,
                                 user: dict = Depends(current_user)):
        require_permission(user, "case.read")
        _load_task_or_404(task_id, user)
        return task_store.events(task_id, tenant_id=user["tid"])

    @app.patch("/ai-tasks/{task_id}")
    async def patch_ai_task(task_id: str, body: dict,
                            user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        row = _load_task_or_404(task_id, user)
        payload = json.loads(row["payload_json"])
        # Optimistic concurrency (if an expected version is supplied). A
        # non-integer expected_task_version is a client error, not a 500.
        if "expected_task_version" in body:
            try:
                expected = int(body["expected_task_version"])
            except (TypeError, ValueError):
                raise HTTPException(400, "expected_task_version must be an "
                                    "integer")
            if expected != payload["task_version"]:
                raise HTTPException(409, "stale task_version")
        # A terminal task cannot be edited; task text cannot set status.
        if payload["task_status"] in ("BLOCKED", "CANCELLED", "EXPIRED",
                                      "NOT_IMPLEMENTED"):
            raise HTTPException(409, f"task is {payload['task_status']} and "
                                "cannot be modified")
        for f in ("task_title", "task_description", "priority", "due_at",
                  "expires_at", "stale_after"):
            if f in body:
                payload[f] = body[f]
        # Untrusted payload can NEVER set status/authority/scopes directly.
        payload["task_version"] += 1
        payload["updated_at"] = utcnow()
        task_store.update(task_id, {
            "payload_json": json.dumps(payload),
            "task_version": payload["task_version"],
            "updated_at": payload["updated_at"]}, tenant_id=user["tid"])
        return payload

    @app.post("/ai-tasks/{task_id}/cancel")
    async def cancel_ai_task(task_id: str,
                             user: dict = Depends(current_user)):
        require_permission(user, "case.update")
        row = _load_task_or_404(task_id, user)
        payload = json.loads(row["payload_json"])
        if payload["task_status"] in ("BLOCKED", "NOT_IMPLEMENTED",
                                      "EXPIRED", "CANCELLED"):
            raise HTTPException(409, f"task is {payload['task_status']}")
        payload["task_status"] = "CANCELLED"
        payload["task_version"] += 1
        now = utcnow()
        task_store.update(task_id, {"task_status": "CANCELLED",
                                    "payload_json": json.dumps(payload),
                                    "task_version": payload["task_version"],
                                    "updated_at": now, "cancelled_at": now},
                          tenant_id=user["tid"])
        task_store.add_event(task_id=task_id, tenant_id=user["tid"],
                             actor_id=user["uid"], actor_type="human",
                             event_type="TASK_CANCELLED")
        return payload

    # ---- UI pages -------------------------------------------------------------------------------------
    ui.mount(app)
    return app
