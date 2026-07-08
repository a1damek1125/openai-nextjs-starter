"""Finalis Portal API — FastAPI over the tested domain core.

UI → these endpoints → domain services (unchanged, 212-test core) →
PortalStore persistence → DbAuditLog (chain in SQL). Providers are the
existing mocks behind real interfaces (env-configurable later).
"""
from __future__ import annotations

import json
import os
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

    @app.get("/admin/me")
    async def admin_me(user: dict = Depends(current_user)):
        uid = rbac_user_id(user)
        m = rbac.membership_of(uid, user["tid"])
        return {"tenant_id": user["tid"], "role": m.role,
                "permissions": sorted(ROLE_PERMISSIONS[m.role])}

    @app.get("/admin/users")
    async def admin_users(user: dict = Depends(current_user)):
        rbac_user_id(user)
        d = rbac.access(actor_type="user", actor_id=f"portal-{user['uid']}",
                        tenant_id=user["tid"], action="tenant.manage_users")
        if d.decision != "ALLOW":
            raise HTTPException(403, "; ".join(d.reasons))
        return [{"id": r["id"], "email": r["email"], "role": r["role"]}
                for r in db.all("SELECT * FROM users WHERE tenant_id=?",
                                user["tid"])]

    @app.post("/admin/users/invite")
    async def admin_invite(body: dict, user: dict = Depends(current_user)):
        uid = rbac_user_id(user)
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
        uid = rbac_user_id(user)
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
            rbac.change_role(target.id, body["role"], actor_user_id=uid)
        except PermissionError as e:
            raise HTTPException(403, str(e))
        db.update("users", target_user_id, {"role": body["role"]})
        return {"role": body["role"]}

    @app.get("/admin/access-logs")
    async def admin_access_logs(user: dict = Depends(current_user)):
        rbac_user_id(user)
        d = rbac.access(actor_type="user", actor_id=f"portal-{user['uid']}",
                        tenant_id=user["tid"], action="access_log.view")
        if d.decision != "ALLOW":
            raise HTTPException(403, "not permitted")
        return [{"event_type": e.event_type, "actor": e.actor,
                 "payload": e.payload, "created_at": e.created_at}
                for e in audit.events(event_type="ACCESS_DECISION")[-50:]]

    # ---- governance visibility (redacted traces from audit) --------------------------
    @app.get("/governance/traces")
    async def governance_traces(user: dict = Depends(current_user)):
        rows = [e for e in audit.events(event_type="AGENT_TRACE")[-50:]]
        return [{"payload": e.payload, "created_at": e.created_at}
                for e in rows]

    @app.get("/governance/blocked")
    async def governance_blocked(user: dict = Depends(current_user)):
        out = []
        for e in audit.events():
            if e.event_type in ("AGENT_TRACE", "CALL_PERMISSION_CHECKED",
                                "FOLLOW_UP_RATE_LIMITED",
                                "CALL_BLOCKED_ANTI_HARASSMENT",
                                "WORKFLOW_STOPPED_WASTE"):
                p = e.payload or {}
                status = p.get("status") or p.get("result") or ""
                if "BLOCK" in str(status) or e.event_type in (
                        "FOLLOW_UP_RATE_LIMITED",
                        "CALL_BLOCKED_ANTI_HARASSMENT",
                        "WORKFLOW_STOPPED_WASTE"):
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
        reasons = p.get("reasons") or [p.get("reason", "policy")]
        return "Action blocked: " + ", ".join(str(r) for r in reasons)

    # ---- scheduling wiring ---------------------------------------------------------------
    from ..scheduling.engine import APPOINTMENT_TYPES, SchedulingEngine
    sched = SchedulingEngine(audit)
    app.state.scheduling = sched

    @app.get("/scheduling/availability")
    async def sched_availability(appointment_type: str = "VIDEO_CALL",
                                 day: Optional[str] = None,
                                 resource_id: Optional[str] = None,
                                 user_: dict = Depends(current_user)):
        d = datetime.fromisoformat(day) if day else \
            datetime.utcnow() + timedelta(days=1)
        slots = sched.available_slots(day=d,
                                      appointment_type=appointment_type,
                                      resource_id=resource_id)
        return json.loads(json.dumps(slots, default=str))

    @app.post("/scheduling/appointments")
    async def sched_book(body: dict, user: dict = Depends(current_user)):
        require_role(user, "owner", "manager", "operator")
        case = load_case_or_404(body["case_id"], user)
        vector = load_vector(case.id)
        try:
            appt, token = sched.book(
                tenant_id=user["tid"], case_id=case.id,
                appointment_type=body.get("appointment_type", "CALLBACK"),
                start_at=datetime.fromisoformat(body["start_at"]),
                user_id=body.get("user_id"),
                resource_id=body.get("resource_id"), vector=vector)
        except ValueError as e:
            raise HTTPException(409, str(e))
        save_vector(case.id, vector)
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
    async def sched_op(appt_id: str, op: str, body: dict,
                       user: dict = Depends(current_user)):
        require_role(user, "owner", "manager", "operator")
        appt = sched.appointments.get(appt_id)
        if appt is None or appt.tenant_id != user["tid"]:
            raise HTTPException(404, "appointment not found")
        vector = load_vector(appt.case_id)
        try:
            if op == "reschedule":
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
        return {"status": appt.status,
                "lifecycle_view": load_vector(appt.case_id)
                .derived_outcome_view()}

    @app.get("/confirm/{token}", response_class=__import__(
        "fastapi.responses", fromlist=["HTMLResponse"]).HTMLResponse)
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
            raise HTTPException(404, "invalid or expired")
        return {"status": appt.status}

    # ---- audit --------------------------------------------------------------------------------------
    @app.get("/audit/verify/{case_id}")
    async def audit_verify(case_id: str,
                           user: dict = Depends(current_user)):
        load_case_or_404(case_id, user)
        fresh = DbAuditLog(db)      # re-read from SQL and verify
        return {"chain_valid": fresh.verify_chain(),
                "events_total": len(fresh.events()),
                "events_case": len(fresh.events(case_id=case_id))}

    # ---- UI pages -------------------------------------------------------------------------------------
    ui.mount(app)
    return app
