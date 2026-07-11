"""Portal UI — server-served pages whose JavaScript calls the real REST API.

No hardcoded dashboard data: every section is fetched from /dashboard/*,
/cases/*, /audit/* with the session token. (A richer Next.js app consumes
the same endpoints later; this shell is the working, browser-testable MVP.)
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

STYLE = """
body{font-family:system-ui,sans-serif;margin:1.5rem;max-width:75rem}
.cards{display:flex;flex-wrap:wrap;gap:.6rem}
.card{border:1px solid #ddd;border-radius:8px;padding:.6rem 1rem;min-width:8rem}
.card b{display:block;font-size:1.3rem}
section{margin:1.2rem 0;border-top:1px solid #eee;padding-top:.6rem}
table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:.25rem .5rem}
button{margin:.15rem;cursor:pointer}.err{color:#c0392b}.ok{color:#27ae60}
.badge{color:#fff;background:#7f8c8d;border-radius:4px;padding:0 .4rem;font-size:.8rem}
input,textarea{width:100%;max-width:28rem;margin:.2rem 0;padding:.3rem}
#loading{color:#7f8c8d;font-style:italic}
"""

LOGIN_PAGE = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Finalis — Login</title><style>{STYLE}</style></head><body>
<h1>Finalis AI</h1><h2 id="login-title">Sign in</h2>
<form id="login-form">
  <input id="email" placeholder="email" value="owner@demo.finalis"/>
  <input id="password" type="password" placeholder="password" value="demo1234"/>
  <button type="submit">Log in</button>
  <p id="login-error" class="err" hidden>Invalid credentials</p>
</form>
<script>
document.getElementById('login-form').onsubmit = async (e) => {{
  e.preventDefault();
  const r = await fetch('/auth/login', {{method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{email: email.value, password: password.value}})}});
  if (!r.ok) {{ document.getElementById('login-error').hidden = false; return; }}
  const data = await r.json();
  localStorage.setItem('finalis_token', data.token);
  localStorage.setItem('finalis_role', data.role);
  location.href = '/portal';
}};
</script></body></html>"""

# Plain strings (single braces) interpolated into the PORTAL_PAGE f-string:
# the wiring sections' JS stays readable instead of double-brace escaped.
WIRING_SECTIONS = """
<section id="sched-section"><h2>Scheduling</h2>
<p><small>Calendar &amp; video providers are <b>mocks</b> — links are
simulated. Appointments are <b>persisted locally</b> (SQLite, migration
v4) and survive restarts. Real Google / Microsoft / Cal.com / LiveKit
providers are <b>not connected</b> (BLOCKED_BY_CREDENTIALS — adapters
ready, credentials pending).</small></p>
<div id="sched-book" hidden>
  Case: <select id="sched-case"></select>
  Type: <select id="sched-type">
    <option>CALLBACK</option><option>PHONE_CALL</option>
    <option>VIDEO_CALL</option><option>SALES_CONSULTATION</option>
    <option>OFFER_REVIEW</option><option>TECHNICIAN_VISIT</option>
    <option>SERVICE_DELIVERY</option><option>POST_SALE_CHECKIN</option>
  </select>
  Day: <input id="sched-day" type="date" style="max-width:11rem"/>
  Resource: <input id="sched-resource" style="max-width:14rem"
    placeholder="tech-1 (required for visits)"/>
  <button id="find-slots" onclick="loadSlots()">Find slots</button>
  <div id="sched-slots"></div>
  <div id="sched-msg"></div>
</div>
<h3>Appointments</h3><div id="sched-appts"></div>
</section>

<section id="admin-section"><h2>Admin — Users &amp; Access</h2>
<p><small>Local demo session — buttons below are convenience only; every
action is re-checked server-side by the RBAC engine.</small></p>
<p id="admin-me"></p>
<p id="admin-denied" hidden><i>Your role cannot manage users
(enforced server-side).</i></p>
<div id="admin-manage" hidden>
  <div id="admin-users"></div>
  <h3>Invite user</h3>
  <input id="invite-email" placeholder="email" style="max-width:16rem"/>
  <select id="invite-role">
    <option>viewer</option><option>technician</option><option>operator</option>
    <option>accountant</option><option>manager</option>
  </select>
  <button id="invite-btn" onclick="inviteUser()">Invite (simulated email)</button>
  <span id="invite-msg"></span>
</div>
<div id="admin-logs-wrap" hidden>
  <h3>Access log (recent decisions)</h3><ul id="admin-logs"></ul>
</div>
</section>

<section id="gov-section" hidden><h2>Governance — AI Activity</h2>
<h3>Blocked actions</h3>
<div id="gov-blocked"></div>
<h3>Agent traces</h3>
<p><small id="gov-traces-note"><b>SCAFFOLDED_ONLY:</b> this endpoint is live,
tenant-scoped and permission-gated, but portal agents are not yet wired
through the governed runtime — the list stays empty until that
producer wiring lands.</small></p>
<div id="gov-traces"></div>
</section>
"""

WIRING_JS = """
const $ = (id) => document.getElementById(id);
const ROLES = ['owner','manager','operator','technician','accountant','viewer'];
const send = async (method, path, body) => {
  const r = await fetch(path, {method, headers: H(),
                               body: body ? JSON.stringify(body) : '{}'});
  return {ok: r.ok, data: await r.json()};
};

window.loadSections = async () => {
  let me; try { me = await get('/admin/me'); } catch (e) { return; }
  window.ME = me;
  const cases = await get('/cases');
  $('admin-me').innerHTML = `Tenant <b>${me.tenant_id}</b> · role
    <b id="me-role">${me.role}</b> · ${me.permissions.length} permissions`;
  // Visibility mirrors permissions; the server re-checks every call.
  const canBook = ['owner','manager','operator'].includes(me.role);
  const canManage = me.permissions.includes('tenant.manage_users');
  const canLogs = me.permissions.includes('access_log.view');
  const canAudit = me.permissions.includes('audit.view');
  $('sched-book').hidden = !canBook;
  $('sched-case').innerHTML = cases.map(c =>
    `<option value="${c.id}">${c.title}</option>`).join('');
  if (!$('sched-day').value) $('sched-day').value =
    new Date(Date.now() + 864e5).toISOString().slice(0, 10);
  $('admin-manage').hidden = !canManage;
  $('admin-denied').hidden = canManage;
  $('admin-logs-wrap').hidden = !canLogs;
  $('gov-section').hidden = !canAudit;
  const jobs = [loadAppts()];
  if (canManage) jobs.push(loadUsers());
  if (canLogs) jobs.push(loadLogs());
  if (canAudit) jobs.push(loadGov());
  if (window.loadQuoteSection) jobs.push(loadQuoteSection(me, cases));
  if (window.loadEvidenceSection)
    jobs.push(loadEvidenceSection(me, cases));
  if (window.loadCrmSection) jobs.push(loadCrmSection(me, cases));
  if (window.loadWorkbenchSection)
    jobs.push(loadWorkbenchSection(me, cases));
  if (window.loadAIEmployeeSection) jobs.push(loadAIEmployeeSection(me));
  if (window.loadTasksSection) jobs.push(loadTasksSection(me));
  if (window.loadRunsSection) jobs.push(loadRunsSection(me));
  if (window.loadApprovalsSection) jobs.push(loadApprovalsSection(me));
  if (window.loadLifecycleSection) jobs.push(loadLifecycleSection(me));
  if (window.loadArtifactsSection) jobs.push(loadArtifactsSection(me));
  if (window.loadToolsSection) jobs.push(loadToolsSection(me));
  if (window.loadQualitySection) jobs.push(loadQualitySection(me));
  if (window.loadContractsSection) jobs.push(loadContractsSection(me));
  if (window.loadActionsSection) jobs.push(loadActionsSection(me));
  if (window.loadBrokerSection) jobs.push(loadBrokerSection(me));
  if (window.loadRuntimeSection) jobs.push(loadRuntimeSection(me));
  if (window.loadWriteIntentSection) jobs.push(loadWriteIntentSection(me));
  if (window.loadCommitSimSection) jobs.push(loadCommitSimSection(me));
  if (window.loadLocalTxSection) jobs.push(loadLocalTxSection(me));
  if (window.loadRecoverySection) jobs.push(loadRecoverySection(me));
  if (window.loadWorkObsSection) jobs.push(loadWorkObsSection(me));
  if (window.loadWorkInboxSection) jobs.push(loadWorkInboxSection(me));
  await Promise.allSettled(jobs);
};

window.loadUsers = async () => {
  const us = await get('/admin/users');
  $('admin-users').innerHTML =
    '<table><tr><th>Email</th><th>Role</th><th>Change role</th></tr>' +
    us.map(u => `<tr><td>${u.email}</td><td>${u.role}</td>
      <td><select id="role-${u.id}">${ROLES.map(r =>
        `<option ${r === u.role ? 'selected' : ''}>${r}</option>`).join('')}
      </select>
      <button onclick="changeRole('${u.id}')">Change</button></td></tr>`)
    .join('') + '</table>';
};
window.changeRole = async (id) => {
  const {ok, data} = await send('PATCH', `/admin/memberships/${id}/role`,
                                {role: $('role-' + id).value});
  $('invite-msg').innerText = ok ? 'Role updated to ' + data.role +
    ' (takes effect on next login)' : 'Refused: ' + data.detail;
  loadUsers(); loadLogs();
};
window.inviteUser = async () => {
  const {ok, data} = await send('POST', '/admin/users/invite',
    {email: $('invite-email').value, role: $('invite-role').value});
  $('invite-msg').innerText = ok ?
    'Invitation ' + data.status + ' (simulated email — no real send)' :
    'Refused: ' + data.detail;
};
window.loadLogs = async () => {
  const logs = await get('/admin/access-logs');
  $('admin-logs').innerHTML = logs.slice(-10).reverse().map(e =>
    `<li><b>${e.payload.decision}</b> ${e.payload.action}
     <small>${e.actor} · ${e.payload.reasons.join(', ')}</small></li>`)
    .join('') || '<li><i>No access decisions yet.</i></li>';
};

window.loadSlots = async () => {
  const q = new URLSearchParams({appointment_type: $('sched-type').value});
  if ($('sched-day').value) q.set('day', $('sched-day').value);
  if ($('sched-resource').value) q.set('resource_id', $('sched-resource').value);
  const r = await fetch('/scheduling/availability?' + q, {headers: H()});
  const slots = await r.json();
  if (!r.ok) { $('sched-slots').innerHTML =
    `<span class="err">${slots.detail || 'error'}</span>`; return; }
  $('sched-slots').innerHTML = slots.length ? 'Free: ' + slots.map(s =>
    `<button onclick="bookSlot('${s.start_at}')">
     ${s.start_at.slice(11, 16)}</button>`).join('') : '<i>No free slots.</i>';
};
window.bookSlot = async (start) => {
  const body = {case_id: $('sched-case').value,
                appointment_type: $('sched-type').value,
                start_at: start.replace(' ', 'T')};
  if ($('sched-resource').value) body.resource_id = $('sched-resource').value;
  const {ok, data} = await send('POST', '/scheduling/appointments', body);
  $('sched-msg').innerHTML = ok ?
    `Booked: <b id="booked-status">${data.status}</b>` +
    (data.video_meeting_url ?
      ` · video link (mock): ${data.video_meeting_url}` : '') +
    (data.confirmation_url ?
      ` · client confirmation link: <a id="confirm-link"
        href="${data.confirmation_url}">${data.confirmation_url}</a>` : '') :
    `<span class="err">Blocked: ${data.detail || ''}</span>`;
  loadAppts();
};
window.loadAppts = async () => {
  const as = await get('/scheduling/appointments');
  const canOp = ['owner','manager','operator'].includes(ME.role);
  $('sched-appts').innerHTML = as.length ?
    '<table><tr><th>Case</th><th>Type</th><th>Start</th><th>Status</th>' +
    '<th></th></tr>' + as.map(a =>
      `<tr data-appt="${a.id}"><td>${a.case_id.slice(0, 8)}</td>
       <td>${a.type}</td><td>${a.start_at}</td><td>${a.status}</td><td>` +
      (canOp ? `<button onclick="apptOp('${a.id}','complete')">Complete</button>
        <button onclick="apptOp('${a.id}','no-show')">No-show</button>
        <button onclick="apptReschedule('${a.id}')">Reschedule</button>
        <button onclick="apptCancel('${a.id}')">Cancel</button>` : '') +
      '</td></tr>').join('') + '</table>' :
    '<i>No appointments yet.</i>';
};
window.apptOp = async (id, op, body) => {
  const {ok, data} = await send('POST',
    `/scheduling/appointments/${id}/${op}`, body || {});
  $('sched-msg').innerText = ok ? op + ' → ' + data.status +
    (data.lifecycle_view ? ' · case is now: ' + data.lifecycle_view : '') :
    'Refused: ' + (data.detail || '');
  loadAppts();
};
window.apptReschedule = (id) => {
  const ns = prompt('New start (YYYY-MM-DDTHH:MM:SS)');
  if (ns) apptOp(id, 'reschedule', {new_start: ns});
};
window.apptCancel = (id) => {
  const reason = prompt('Cancellation reason (required)');
  if (reason !== null) apptOp(id, 'cancel', {reason: reason, by: 'company'});
};
window.scheduleFor = (id) => {
  $('sched-case').value = id;
  $('sched-section').scrollIntoView();
};

window.loadGov = async () => {
  const blocked = await get('/governance/blocked');
  $('gov-blocked').innerHTML = blocked.length ? blocked.map(b =>
    `<div class="card"><span class="badge">${b.event}</span>
     <p>${b.explanation}</p></div>`).join('') :
    '<i>No blocked AI actions for this tenant.</i>';
  const traces = await get('/governance/traces');
  $('gov-traces').innerHTML = traces.length ?
    '<table><tr><th>Action</th><th>Tool</th><th>Status</th><th>Policy</th>' +
    '<th>When</th></tr>' + traces.slice(-15).reverse().map(t =>
      `<tr><td>${t.payload.action}</td><td>${t.payload.tool}</td>
       <td>${t.payload.status}</td><td>${t.payload.policy || '-'}</td>
       <td><small>${t.created_at}</small></td></tr>`).join('') + '</table>' :
    '<i>No agent traces yet (producer wiring pending).</i>';
};
"""

QUOTES_SECTIONS = """
<section id="quotes-section"><h2>Quotes</h2>
<p><small>Tax engine, PDF generator and invoice handoff are <b>mocks</b>
(MOCKED_AND_TESTED — no real Stripe / invoicing / payment provider is
connected). E-signature is SCAFFOLDED_ONLY. Quote options are
SCAFFOLDED_ONLY (not persisted). Change-order approval API is MISSING
(engine-only, future mission). Quote-to-invoice conversion is a
placeholder domain event only. <b>An accepted quote does not mean the
case is completed</b> — it only opens payment and fulfillment
requirements.</small></p>
<div id="quote-create" hidden>
  Case: <select id="quote-case"></select>
  <button id="quote-create-btn" onclick="createQuote()">Create quote draft</button>
</div>
<div id="quote-msg"></div>
<div id="quote-list"><i>Loading quotes…</i></div>
<div id="quote-detail"></div>
</section>

<section id="pricing-admin" hidden><h2>Pricing Admin (minimal)</h2>
<p><small>Local price book + pricing rules — deliberately minimal, not an
ERP settings module.</small></p>
<div id="pricing-books"></div>
<input id="pb-sku" placeholder="SKU" style="max-width:8rem"/>
<input id="pb-name" placeholder="name" style="max-width:10rem"/>
<input id="pb-price" placeholder="list price" style="max-width:8rem"/>
<button id="pb-add" onclick="addPriceBookItem()">Add price book item</button>
<div id="pricing-rules"></div>
<span id="pricing-msg"></span>
</section>
"""

QUOTES_JS = """
const QSTATE_HELP = {
  DRAFT: 'DRAFT — editable.',
  NEEDS_MORE_INFO: 'Needs more info before pricing.',
  PRICE_CALCULATED: 'Price calculated — editing returns it to DRAFT.',
  APPROVAL_REQUIRED: 'Waiting for human approval.',
  APPROVED: 'Approved — ready to send.',
  REJECTED_BY_APPROVER: 'Rejected by approver — back to draft to fix.',
  SENT: 'This quote is already sent and cannot be edited. Create a revision.',
  VIEWED: 'Client viewed the quote. Content is frozen.',
  ACCEPTED: 'This quote is accepted and immutable. Use a change order. ' +
    'The case is NOT completed — payment and fulfillment are still open.',
  DECLINED: 'Client declined. Revise to try again.',
  EXPIRED: 'Validity expired — revise to re-offer.',
  CANCELLED: 'Cancelled.',
  REVISED: 'Superseded by a newer version once it is sent.',
  SUPERSEDED: 'Replaced by a newer sent version.',
  CONVERTED_TO_INVOICE: 'Handed to invoicing (mock handoff only).'
};
const canQuote = () => ME && ME.permissions.includes('offer.create');
const canApprove = () => ME && ME.permissions.includes('offer.approve');
const qmsg = (t, ok) => { $('quote-msg').innerHTML =
  `<span class="${ok ? 'ok' : 'err'}">${t}</span>`; };

window.loadQuoteSection = async (me, cases) => {
  $('quote-create').hidden = !canQuote();
  $('quote-case').innerHTML = cases.map(c =>
    `<option value="${c.id}">${c.title}</option>`).join('');
  $('pricing-admin').hidden = !canQuote();
  await loadQuotes();
  if (canQuote()) await loadPricingAdmin();
};

window.loadQuotes = async (caseId) => {
  const qs = await get('/quotes' + (caseId ? '?case_id=' + caseId : ''));
  $('quote-list').innerHTML = qs.length ?
    '<table><tr><th>Quote</th><th>Case</th><th>Status</th><th>v</th>' +
    '<th>Total</th><th></th></tr>' + qs.map(q =>
      `<tr data-quote="${q.id}"><td>${q.id.slice(0, 8)}</td>
       <td>${q.case_id.slice(0, 8)}</td><td>${q.state}</td>
       <td>${q.version}</td><td>${q.total} ${q.currency}</td>
       <td><button onclick="openQuote('${q.id}')">Open</button></td>
       </tr>`).join('') + '</table>' :
    '<i>No quotes yet.</i>';
};

window.createQuote = async () => {
  const {ok, data} = await send('POST', '/quotes',
                                {case_id: $('quote-case').value});
  qmsg(ok ? 'Draft created.' : 'Refused: ' + data.detail, ok);
  if (ok) { await loadQuotes(); openQuote(data.id); }
};

window.quotesFor = (caseId) => {
  loadQuotes(caseId);
  if ($('quote-case')) $('quote-case').value = caseId;
  $('quotes-section').scrollIntoView();
};

window.openQuote = async (id) => {
  const q = await get('/quotes/' + id);
  const ps = ME.permissions.includes('payment.view')
    ? await get('/quotes/' + id + '/payment-schedule') : null;
  const cos = q.state === 'ACCEPTED'
    ? await get('/quotes/' + id + '/change-orders') : [];
  const lines = q.line_items.map(li =>
    `<tr><td>${li.description}</td><td>${li.quantity}</td>
     <td>${li.line_cost}</td><td>${li.price_after_discount}</td>
     <td>${li.applied_discount}</td>
     <td>${li.margin_percent ?? '?'}</td><td>${li.line_total}</td>
     <td>${li.requires_human_review ? 'needs human review' : ''}</td>
     </tr>`).join('');
  const schedule = (ps && ps.milestones.length) ? ps.milestones.map(m =>
    `<li>${m.label}: ${(parseFloat(m.fraction) * 100).toFixed(0)}%
     (${m.trigger})${m.blocks_fulfillment_until_paid
       ? ' — <b>fulfillment blocked until paid</b>' : ''}</li>`)
    .join('') : '<li><i>No schedule — full amount on acceptance.</i></li>';
  const reqs = (ps && ps.payment_requirements.length)
    ? '<p><b>Payment requirements (from acceptance):</b> ' +
      ps.payment_requirements.map(r => `${r.label}: ${r.amount}`)
        .join(' · ') + '</p>' : '';
  const editable = q.editable || q.state === 'PRICE_CALCULATED';
  const buttons = [];
  if (canQuote() && editable)
    buttons.push(`<button onclick="calcQuote('${id}')">Calculate</button>`);
  if (canApprove() && ['PRICE_CALCULATED', 'APPROVAL_REQUIRED']
      .includes(q.state)) {
    buttons.push(`<button onclick="qAct('${id}','approve')">Approve</button>`);
    buttons.push(`<button onclick="qReject('${id}')">Reject</button>`);
  }
  if (canQuote() && ['PRICE_CALCULATED', 'APPROVED'].includes(q.state))
    buttons.push(`<button onclick="qAct('${id}','send')">Send</button>`);
  if (canQuote() && ['SENT', 'VIEWED'].includes(q.state)) {
    buttons.push(`<button onclick="qAct('${id}','accept')">Client accepts (simulated)</button>`);
    buttons.push(`<button onclick="qDecline('${id}')">Client declines…</button>`);
    buttons.push(`<button onclick="qAct('${id}','expire')">Expire</button>`);
  }
  if (canQuote() && ['SENT', 'VIEWED', 'DECLINED', 'EXPIRED']
      .includes(q.state))
    buttons.push(`<button onclick="qAct('${id}','revise')">Revise (new version)</button>`);
  buttons.push(`<button onclick="qPdf('${id}')">Generate mock PDF</button>`);
  $('quote-detail').innerHTML = `
    <h3>Quote ${q.id.slice(0, 8)} — v${q.version}
      <span class="badge" id="quote-state">${q.state}</span></h3>
    <p><i id="quote-state-help">${QSTATE_HELP[q.state] || ''}</i></p>
    <p>Subtotal ${q.subtotal} · Tax ${q.tax_total} (mock tax engine) ·
       <b>Total ${q.total} ${q.currency}</b></p>
    <p><b>Assumptions:</b> ${q.assumptions.join('; ') || '<i>none yet</i>'}
       · <b>Exclusions:</b> ${q.exclusions.join('; ') || '<i>none yet</i>'}
       · Terms template: ${q.terms_template_approved
         ? 'approved' : '<b>not approved — send will require approval</b>'}</p>
    <table><tr><th>Item</th><th>Qty</th><th>Cost</th><th>Unit price</th>
      <th>Discount</th><th>Margin</th><th>Total</th><th></th></tr>
      ${lines || '<tr><td colspan=8><i>no lines yet</i></td></tr>'}</table>
    ${canQuote() && editable ? `
      <p id="quote-line-form">
        <input id="ql-desc" placeholder="description" style="max-width:12rem"/>
        <input id="ql-cost" placeholder="cost" style="max-width:6rem"/>
        <input id="ql-price" placeholder="book price" style="max-width:6rem"/>
        <input id="ql-discount" placeholder="discount" style="max-width:6rem"/>
        <input id="ql-reason" placeholder="discount reason" style="max-width:10rem"/>
        <button id="ql-add" onclick="addQuoteLine('${id}')">Add line</button>
        <button onclick="setTerms('${id}')">Set assumptions/exclusions/terms</button>
        <button onclick="setDeposit('${id}')">Set 30% deposit schedule</button>
      </p>` : `<p><i>${q.state === 'ACCEPTED'
        ? 'Accepted quotes change only via change orders below.'
        : 'This quote is not editable in its current state.'}</i></p>`}
    <div id="quote-calc"></div>
    <p><b>Payment schedule:</b></p><ul>${schedule}</ul>${reqs}
    <p>${buttons.join(' ')}</p>
    ${q.state === 'ACCEPTED' ? `
      <h4>Change orders <small>(approval API is MISSING — engine-only,
        future mission)</small></h4>
      <ul>${cos.map(c => `<li>${c.description}: ${c.price_delta}
        (margin ${c.margin_percent ?? '?'}) — ${c.status}</li>`).join('')
        || '<li><i>none</i></li>'}</ul>
      <p><input id="co-desc" placeholder="description" style="max-width:12rem"/>
      <input id="co-price" placeholder="price delta" style="max-width:6rem"/>
      <input id="co-cost" placeholder="cost delta" style="max-width:6rem"/>
      <button id="co-add" onclick="addChangeOrder('${id}')">Create change order</button></p>`
      : ''}
    <div id="quote-pdf"></div>
    <h4>Quote events</h4><ul id="quote-events"><li><i>…</i></li></ul>`;
  if (ME.permissions.includes('audit.view')) {
    const evs = await get('/quotes/' + id + '/events');
    $('quote-events').innerHTML = evs.slice(-10).reverse().map(e =>
      `<li>${e.event_type} <small>${e.created_at}</small></li>`).join('')
      || '<li><i>none</i></li>';
  } else { $('quote-events').innerHTML = '<li><i>needs audit.view</i></li>'; }
};

window.addQuoteLine = async (id) => {
  const body = {description: $('ql-desc').value};
  if ($('ql-cost').value) body.material_cost = $('ql-cost').value;
  if ($('ql-price').value) body.price_book_price = $('ql-price').value;
  if ($('ql-discount').value) body.requested_discount = $('ql-discount').value;
  if ($('ql-reason').value) body.discount_reason = $('ql-reason').value;
  const {ok, data} = await send('POST', `/quotes/${id}/lines`, body);
  qmsg(ok ? 'Line added.' : 'Refused: ' + data.detail, ok);
  if (ok) openQuote(id);
};

window.setTerms = async (id) => {
  const {ok, data} = await send('PATCH', '/quotes/' + id, {
    assumptions: ['single-day install', 'existing electrical is adequate'],
    exclusions: ['electrical rework', 'wall repairs'],
    terms_template_id: 'hvac-standard-v1', terms_template_approved: true});
  qmsg(ok ? 'Assumptions, exclusions and approved terms template set.'
          : 'Refused: ' + data.detail, ok);
  if (ok) openQuote(id);
};

window.setDeposit = async (id) => {
  const {ok, data} = await send('POST', `/quotes/${id}/payment-schedule`, {
    milestones: [
      {label: 'deposit', fraction: '0.3', is_deposit: true,
       blocks_fulfillment_until_paid: true},
      {label: 'final', fraction: '0.7', trigger: 'on_completion'}]});
  qmsg(ok ? 'Deposit schedule set (30/70).' : 'Refused: ' + data.detail, ok);
  if (ok) openQuote(id);
};

window.calcQuote = async (id) => {
  const {ok, data} = await send('POST', `/quotes/${id}/calculate`, {});
  if (!ok) { qmsg('Refused: ' + data.detail, false); return; }
  const gates = Object.entries(data.gates).map(([name, g]) =>
    `<li><b>${name}</b>: ${g.decision}${g.reasons.length
      ? ' — ' + g.reasons.join('; ') : ''}</li>`).join('');
  // Re-render the detail FIRST — it resets #quote-calc, so filling the
  // panel before the re-render would flash and vanish.
  await openQuote(id);
  $('quote-calc').innerHTML = `
    <p id="calc-totals">Calculated: subtotal ${data.subtotal} ·
      tax ${data.tax_total} (mock) · <b>total ${data.total}</b></p>
    <ul id="calc-gates">${gates}</ul>
    <p id="calc-scores">Price confidence: ${data.scores.price_confidence}
      · Evidence coverage: ${data.scores.evidence_coverage}
      <small>(risk &amp; clarity scores need case-context wiring —
      SCAFFOLDED_ONLY in the portal)</small></p>`;
};

window.qAct = async (id, action) => {
  const {ok, data} = await send('POST', `/quotes/${id}/${action}`, {});
  if (ok && action === 'accept') {
    qmsg('Accepted. Payment requirements created: ' +
      data.payment_requirements.map(r => `${r.label} ${r.amount}`)
        .join(' · ') +
      '. Case is now ' + data.lifecycle_view +
      ' — NOT completed yet.', true);
  } else {
    qmsg(ok ? action + ' → ' + data.state : 'Refused: ' + data.detail, ok);
  }
  await loadQuotes();
  openQuote(ok && data.id ? data.id : id);
};

window.qReject = async (id) => {
  const reason = prompt('Rejection reason (required)');
  if (reason === null) return;
  const {ok, data} = await send('POST', `/quotes/${id}/reject`,
                                {reason: reason});
  qmsg(ok ? 'Rejected.' : 'Refused: ' + data.detail, ok);
  openQuote(id);
};

window.qDecline = async (id) => {
  const reason = prompt('Decline reason (required)');
  if (reason === null) return;
  const {ok, data} = await send('POST', `/quotes/${id}/decline`,
                                {reason: reason});
  qmsg(ok ? 'Declined.' : 'Refused: ' + data.detail, ok);
  openQuote(id);
};

window.qPdf = async (id) => {
  const {ok, data} = await send('POST', `/quotes/${id}/generate-pdf`, {});
  if (!ok) { qmsg('Refused: ' + data.detail, false); return; }
  const f = document.createElement('iframe');
  f.style.width = '100%'; f.style.height = '16rem';
  f.srcdoc = data.html;
  $('quote-pdf').innerHTML =
    `<p id="pdf-label"><b>MOCK_PDF_PROVIDER</b> — document
     ${data.document_id.slice(0, 8)} (HTML placeholder, not a real PDF):</p>`;
  $('quote-pdf').appendChild(f);
};

window.addChangeOrder = async (id) => {
  const {ok, data} = await send('POST', `/quotes/${id}/change-orders`, {
    description: $('co-desc').value, price_delta: $('co-price').value,
    cost_delta: $('co-cost').value || '0'});
  qmsg(ok ? `Change order created (${data.status}, margin
    ${data.margin_percent ?? '?'}).` : 'Refused: ' + data.detail, ok);
  if (ok) openQuote(id);
};

window.loadPricingAdmin = async () => {
  const books = await get('/price-books');
  let book = books[0];
  if (!book) {
    const r = await send('POST', '/price-books', {name: 'default'});
    if (r.ok) book = r.data;
  }
  if (!book) { $('pricing-books').innerHTML = ''; return; }
  window.PB_ID = book.id;
  const items = await get(`/price-books/${book.id}/items`);
  $('pricing-books').innerHTML = `<p><b>Price book:</b> ${book.name}</p>` +
    (items.length ? '<table><tr><th>SKU</th><th>Name</th><th>List price</th>'
      + '</tr>' + items.map(i => `<tr><td>${i.sku}</td><td>${i.name}</td>
      <td>${i.list_price}</td></tr>`).join('') + '</table>'
      : '<i>No items yet.</i>');
  const rules = await get('/pricing-rules');
  $('pricing-rules').innerHTML = rules.length ?
    '<p><b>Pricing rules:</b></p><ul>' + rules.map(r =>
      `<li>${r.name}: ${r.discount_percent}% off ${r.applies_to_sku}
       (min qty ${r.min_quantity})</li>`).join('') + '</ul>' :
    '<p><i>No pricing rules.</i></p>';
};

window.addPriceBookItem = async () => {
  if (!window.PB_ID) return;
  const {ok, data} = await send('POST', `/price-books/${PB_ID}/items`, {
    sku: $('pb-sku').value, name: $('pb-name').value,
    list_price: $('pb-price').value});
  $('pricing-msg').innerText = ok ? 'Item saved.'
    : 'Refused: ' + data.detail;
  loadPricingAdmin();
};
"""

EVIDENCE_SECTIONS = """
<section id="evidence-section"><h2>Evidence Command Center</h2>
<p><small><b>Documents provide facts, never commands.</b> Quarantine-first
upload · original filename is metadata only · Content-Type is not trusted ·
<b>No public raw download</b> · hard blockers override scores, always.
Storage: LocalEvidenceStorageProvider (local dev storage, <b>no native
WORM/Object Lock</b>). Scanner/CDR: <b>mock</b> (MOCKED_AND_TESTED, not
production antivirus). OCR: <b>NOT RUN</b> (SCAFFOLDED_ONLY). Docling /
PaddleOCR / MinerU / C2PA / ClamAV / MinIO / S3 are <b>not connected</b>.
NOT production-ready.</small></p>
<div class="cards" id="ev-dashboard"></div>
<div id="ev-upload-panel" hidden>
  <h3>Quarantine-first upload</h3>
  Case: <select id="ev-case"></select>
  Type: <select id="ev-type">
    <option>document</option><option>payment_proof</option>
    <option>fulfillment_photo</option><option>completion_protocol</option>
    <option>acceptance_evidence</option><option>scope_delta_evidence</option>
  </select>
  Sensitivity: <select id="ev-sensitivity">
    <option>normal</option><option>sensitive</option>
  </select>
  <input id="ev-filename" value="notatka.txt" style="max-width:12rem"/>
  <textarea id="ev-content" placeholder="file content (demo text upload)"
    style="max-width:28rem"></textarea>
  <button id="ev-upload-btn" onclick="evUpload()">Upload to quarantine</button>
  <button onclick="evUploadSession()">Prepare upload session
    (SCAFFOLDED_ONLY, future TUS)</button>
  <span id="ev-session-info"></span>
</div>
<div id="ev-msg"></div>
<h3>Evidence</h3><div id="ev-list"><i>Loading evidence…</i></div>
<div id="ev-detail"></div>

<h3>Decision Completeness Matrix</h3>
<p><small>Requirement profiles per critical decision — computed by
<code>/evidence/requirement-check</code>, never by the UI.</small></p>
<p>Evidence for check: <span id="ev-selected">none selected</span>
  <label><input type="checkbox" id="ev-human-verified"/> human-verified
  fallback</label>
  <button id="ev-matrix-btn" onclick="runMatrix()">Run completeness
  matrix</button></p>
<div id="ev-matrix"></div>

<h3>Decision Contract + Causal Action Guard</h3>
<p><small>Critical actions need <b>user intent + admissible facts</b> —
never document instructions. A document may provide facts, never
commands.</small></p>
<p>
  Decision: <select id="ev-decision">
    <option>PAYMENT_MARK_PAID</option><option>QUOTE_ACCEPT</option>
    <option>FULFILLMENT_COMPLETED</option><option>WON_COMPLETED</option>
    <option>CHANGE_ORDER_APPROVAL</option><option>MESSAGE_SEND</option>
  </select>
  <input id="ev-intent" placeholder="user intent reference (empty = none)"
    style="max-width:18rem"/>
  <label><input type="checkbox" id="ev-doc-caused"/> action would NOT
  survive without untrusted document text</label>
  <button id="ev-contract-btn" onclick="runContract()">Validate decision
  contract</button>
</p>
<div id="ev-contract"></div>
</section>
"""

EVIDENCE_JS = """
const esc = (s) => String(s ?? '').replace(/&/g, '&amp;')
  .replace(/</g, '&lt;').replace(/>/g, '&gt;');
window.EV_SELECTED = [];
const evmsg = (t, ok) => { $('ev-msg').innerHTML =
  `<span class="${ok ? 'ok' : 'err'}">${esc(t)}</span>`; };

// Hard Blocker Proof: business meaning + overridability (display only —
// the server decided; this table explains what can happen next).
const BLOCKER_HELP = [
  ['tenant mismatch', 'override impossible — evidence belongs to another tenant'],
  ['case mismatch', 'override impossible — wrong case'],
  ['checksum', 'override impossible until re-upload and re-verification'],
  ['integrity', 'override impossible until re-upload and re-verification'],
  ['malware', 'no override — file must be rejected'],
  ['quarantined', 'cannot support a decision yet — scan and review first'],
  ['rejected', 'needs an explicit new human review to be reconsidered'],
  ['legal hold', 'blocks hard deletion until the hold is released'],
  ['sensitive', 'needs permission or compliance clearance'],
];
const blockerHelp = (b) => (BLOCKER_HELP.find(([k]) =>
  b.toLowerCase().includes(k)) || [null, 'human review required'])[1];

window.loadEvidenceSection = async (me, cases) => {
  $('ev-upload-panel').hidden =
    !me.permissions.includes('document.upload');
  $('ev-case').innerHTML = cases.map(c =>
    `<option value="${c.id}">${esc(c.title)}</option>`).join('');
  await loadEvidence();
};

window.loadEvidence = async (caseId) => {
  const rows = await get('/evidence' + (caseId ? '?case_id=' + caseId : ''));
  const counts = {};
  rows.forEach(r => counts[r.state] = (counts[r.state] || 0) + 1);
  $('ev-dashboard').innerHTML = [
    ['total', rows.length], ['quarantined', counts.QUARANTINED || 0],
    ['admissible', (counts.ADMISSIBLE || 0)
      + (counts.ADMISSIBLE_WITH_LIMITS || 0)],
    ['rejected', counts.REJECTED || 0],
    ['integrity failed', counts.INTEGRITY_FAILED || 0],
    ['legal hold', counts.LEGAL_HOLD || 0],
    ['needs review', counts.NEEDS_HUMAN_REVIEW || 0]]
    .map(([k, v]) => `<div class="card"><b>${v}</b><span>${k}</span></div>`)
    .join('');
  $('ev-list').innerHTML = rows.length ?
    '<table><tr><th></th><th>File</th><th>Type</th><th>State</th>' +
    '<th></th></tr>' + rows.map(r =>
      `<tr data-ev="${r.id}"><td><input type="checkbox"
        onchange="evToggle('${r.id}', this.checked)"/></td>
       <td>${esc(r.original_filename)}</td><td>${r.evidence_type}</td>
       <td>${r.state}</td>
       <td><button onclick="openEvidence('${r.id}')">Open</button></td>
       </tr>`).join('') + '</table>' :
    '<i>No evidence yet — everything starts in quarantine.</i>';
};

window.evToggle = (id, on) => {
  EV_SELECTED = on ? [...EV_SELECTED, id]
                   : EV_SELECTED.filter(x => x !== id);
  $('ev-selected').innerText = EV_SELECTED.length
    ? EV_SELECTED.length + ' selected' : 'none selected';
};

window.evUpload = async () => {
  const content = $('ev-content').value || 'demo evidence content';
  const {ok, data} = await send('POST', '/evidence/upload', {
    case_id: $('ev-case').value, filename: $('ev-filename').value,
    mime: 'text/plain',
    content_b64: btoa(unescape(encodeURIComponent(content))),
    evidence_type: $('ev-type').value,
    sensitivity: $('ev-sensitivity').value,
    text_preview: content});
  evmsg(ok ? 'Uploaded to quarantine (sha256 ' +
        data.integrity.sha256.slice(0, 12) + '…).'
      : 'Refused: ' + data.detail, ok);
  if (ok) { loadEvidence(); openEvidence(data.id); }
};

window.evUploadSession = async () => {
  const {ok, data} = await send('POST', '/evidence/upload-sessions', {
    case_id: $('ev-case').value, filename: $('ev-filename').value,
    expected_size: 1024});
  $('ev-session-info').innerText = ok ?
    `session ${data.id.slice(0, 8)} · ${data.status} · expires ` +
    data.expires_at.slice(0, 16) : 'Refused: ' + data.detail;
};

window.evidenceFor = (caseId) => {
  if ($('ev-case')) $('ev-case').value = caseId;
  loadEvidence(caseId);
  $('evidence-section').scrollIntoView();
};

function readinessIndex(ev, hardBlockers) {
  // UI-ONLY explanatory value — NON-AUTHORITATIVE; the server decides.
  if (hardBlockers && hardBlockers.length) return {value: 0, parts: [
    'hard blocker present → index forced to 0']};
  const admissible = {ADMISSIBLE: 1, ADMISSIBLE_WITH_LIMITS: .8,
                      LEGAL_HOLD: .8, RETENTION_LOCKED: .8,
                      SCANNED_CLEAN: .5, NEEDS_HUMAN_REVIEW: .3};
  const parts = {
    requirement_coverage: ev.evidence_type === 'document' ? 0.5 : 1,
    admissibility_confidence: admissible[ev.state] || 0,
    trust: ev.human_verified ? 1 : 0.6,
    chain: 1,
    integrity: ev.integrity && ev.integrity.valid ? 1 : 0,
    freshness: 1};
  const value = 0.25 * parts.requirement_coverage
    + 0.20 * parts.admissibility_confidence + 0.20 * parts.trust
    + 0.15 * parts.chain + 0.10 * parts.integrity
    + 0.10 * parts.freshness;
  return {value: Math.round(value * 100) / 100,
          parts: Object.entries(parts).map(([k, v]) => `${k}=${v}`)};
}

window.openEvidence = async (id) => {
  const ev = await get('/evidence/' + id);
  const chain = await get(`/evidence/${id}/chain`);
  const perms = ME.permissions;
  const idx = readinessIndex(ev, []);
  const controls = [];
  if (perms.includes('document.analyze')) {
    controls.push(`<button onclick="evReview('${id}','SCANNED_CLEAN')">
      Run mock scan</button>`);
    for (const v of ['ADMISSIBLE', 'ADMISSIBLE_WITH_LIMITS', 'REJECTED',
                     'NEEDS_HUMAN_REVIEW'])
      controls.push(`<button onclick="evReview('${id}','${v}')">
        ${v.replaceAll('_', ' ').toLowerCase()}</button>`);
    controls.push(`<button onclick="evIntegrity('${id}')">
      Verify integrity</button>`);
  }
  if (perms.includes('override.compliance_review'))
    controls.push(`<button onclick="evHold('${id}')">Place legal
      hold</button>`);
  if (perms.includes('document.delete')) {
    controls.push(`<button onclick="evDelete('${id}', false)">Soft delete
      decision</button>`);
    controls.push(`<button onclick="evDelete('${id}', true)">Hard delete
      decision</button>`);
  }
  $('ev-detail').innerHTML = `
    <h4>Evidence ${id.slice(0, 8)}
      <span class="badge" id="ev-state">${ev.state}</span></h4>
    <p>${esc(ev.original_filename)} · ${ev.evidence_type} ·
      sensitivity ${ev.sensitivity} ·
      sha256 <code>${ev.integrity ? ev.integrity.sha256.slice(0, 16)
        : '?'}…</code>
      (${ev.integrity && ev.integrity.valid ? 'integrity OK'
        : '<b class="err">INTEGRITY FAILED</b>'})
      · scan: ${ev.scan.status} (${ev.scan.is_mock ? 'MOCK scanner'
        : ev.scan.provider})
      · injection risk ${ev.injection_risk}
      ${ev.legal_hold ? ' · <b>LEGAL HOLD</b>' : ''}</p>
    <p id="ev-readiness"><b>Evidence Readiness Index (UI-only,
      NON-AUTHORITATIVE — hard blockers override scores; the server
      decision is final):</b> ${idx.value}
      <small>[${idx.parts.join(', ')}]</small></p>
    <p>${controls.join(' ')}</p>
    <div id="ev-blockers"></div>
    <h4>Dual-View <small>— Agent view is intentionally different from
      human view.</small></h4>
    <div style="display:flex;gap:1rem;flex-wrap:wrap">
      <div id="ev-human-view" style="flex:1;min-width:16rem"><i>…</i></div>
      <div id="ev-agent-view" style="flex:1;min-width:16rem"><i>…</i></div>
    </div>
    <h4>AI Access Safety</h4>
    <p><small>Document text is never an operational command.</small>
      <button onclick="evAiAccess('${id}', {})">AI asks: derivative</button>
      <button onclick="evAiAccess('${id}', {requested_raw: true})">AI asks:
        RAW</button>
      <button onclick="evAiAccess('${id}',
        {task_scoped_authorization: true})">AI asks: with task
        scope</button></p>
    <div id="ev-ai-panel"></div>
    <h4>Chain of custody (${chain.length})</h4>
    <ul id="ev-chain">${chain.slice(-12).map(c =>
      `<li>${c.event_type} <small>${esc(c.actor)} ·
       ${c.created_at.slice(0, 19)}</small></li>`).join('')}</ul>`;
  loadDualViews(id);
};

window.loadDualViews = async (id) => {
  try {
    const hv = await get(`/evidence/${id}/human-view`);
    $('ev-human-view').innerHTML = `<p><b>Human view</b><br>
      file: ${esc(hv.original_filename)}<br>
      original reference: <code>${esc(hv.original_reference)}</code><br>
      <small class="err">${esc(hv.untrusted_content_warning)}</small></p>`;
  } catch (e) {
    $('ev-human-view').innerHTML =
      '<i>Human view restricted (permission required).</i>';
  }
  const av = await get(`/evidence/${id}/agent-view`);
  $('ev-agent-view').innerHTML = `<p><b>Agent view</b>
    (restricted by design)<br>
    untrusted: <b>${av.untrusted}</b> — sticky marker; storage never
    launders trust<br>
    symbols: ${av.symbols.map(s => `${s.kind}
      [${s.trusted ? 'trusted: ' + esc(s.human_verified_for)
        : 'UNTRUSTED (' + esc(s.origin) + ')'}]
      ${!s.trusted ? `<button onclick="verifySymbol('${av.evidence_id}',
        '${s.id}')">verify for narrow purpose…</button>` : ''}`)
      .join('; ') || '<i>none</i>'}<br>
    safe derivative: ${av.safe_derivative_text
      ? esc(av.safe_derivative_text)
      : '<i>SCAFFOLDED_ONLY — safe derivative generation comes later for '
        + 'binary files</i>'}<br>
    confidence: ${av.confidence}<br>
    <small>${esc(av.note)}</small></p>`;
};

window.verifySymbol = async (evId, symbolId) => {
  const purpose = prompt('Narrow factual purpose (e.g. invoice amount '
    + 'only)');
  if (!purpose) return;
  const {ok, data} = await send('POST',
    `/evidence/${evId}/human-verify-symbol`,
    {symbol_id: symbolId, purpose});
  evmsg(ok ? 'Symbol verified for: ' + data.human_verified_for
           : 'Refused: ' + data.detail, ok);
  if (ok) loadDualViews(evId);
};

window.evReview = async (id, verdict) => {
  const {ok, data} = await send('POST', `/evidence/${id}/review`,
                                {verdict});
  if (ok) {
    evmsg('Review: ' + data.state + (data.scan.is_mock
      ? ' (mock scanner — not production antivirus)' : ''), true);
  } else {
    evmsg('Refused: ' + data.detail, false);
    $('ev-blockers').innerHTML = `<p><b>Hard Blocker Proof:</b>
      ${esc(data.detail)} — <i>${blockerHelp(data.detail)}</i>.
      Scores cannot override this.</p>`;
  }
  loadEvidence(); openEvidence(id);
};

window.evIntegrity = async (id) => {
  const {ok, data} = await send('POST',
    `/evidence/${id}/verify-integrity`, {});
  evmsg(ok ? 'Integrity ' + (data.valid ? 'VALID' : 'FAILED — evidence '
    + 'is now blocked everywhere') : 'Refused: ' + data.detail,
    ok && data.valid);
  openEvidence(id);
};

window.evHold = async (id) => {
  const reason = prompt('Legal hold reason (required)');
  if (!reason) return;
  const {ok, data} = await send('POST', `/evidence/${id}/legal-hold`,
                                {action: 'place', reason});
  evmsg(ok ? 'Legal hold placed — hard deletion is now blocked.'
           : 'Refused: ' + data.detail, ok);
  openEvidence(id);
};

window.evDelete = async (id, hard) => {
  const {ok, data} = await send('POST',
    `/evidence/${id}/delete-decision`, {hard});
  evmsg(ok ? `Delete decision: ${data.decision} — ` +
        data.reasons.join('; ') : 'Refused: ' + data.detail,
        ok && data.decision.startsWith('ALLOW'));
  loadEvidence(); openEvidence(id);
};

window.evAiAccess = async (id, opts) => {
  const {ok, data} = await send('POST',
    `/evidence/${id}/ai-access-decision`, opts);
  if (!ok) { evmsg('Refused: ' + data.detail, false); return; }
  $('ev-ai-panel').innerHTML = `<p>
    decision: <b>${data.decision}</b> · allowed view:
    ${data.allowed_view} · task scope: ${esc(data.task_scope)}<br>
    reasons: ${data.reasons.map(esc).join('; ')}<br>
    access event: <code>${data.access_event_id.slice(0, 8)}</code> ·
    raw content included: <b>${data.raw_content_included}</b><br>
    <small>Document text is never an operational command.</small></p>`;
};

window.runMatrix = async () => {
  const decisions = ['QUOTE_ACCEPT', 'PAYMENT_MARK_PAID',
    'FULFILLMENT_COMPLETED', 'WON_COMPLETED', 'CHANGE_ORDER_APPROVAL',
    'COMPLAINT_RESOLVED', 'WARRANTY_DECISION'];
  const rows = [];
  for (const d of decisions) {
    const {data} = await send('POST', '/evidence/requirement-check', {
      decision_type: d, evidence_ids: EV_SELECTED,
      human_verified: $('ev-human-verified').checked});
    rows.push(`<tr><td>${d}</td>
      <td>${data.missing.map(esc).join('; ') || '—'}</td>
      <td>${data.admissible.length}</td>
      <td>${data.reasons.map(esc).join('; ') || '—'}</td>
      <td class="${data.allowed ? 'ok' : 'err'}">
        ${data.allowed ? 'READY' : 'BLOCKED'}</td></tr>`);
  }
  $('ev-matrix').innerHTML = '<table><tr><th>Decision</th>' +
    '<th>Missing evidence</th><th>Admissible</th><th>Notes</th>' +
    '<th>Result</th></tr>' + rows.join('') + '</table>';
};

window.runContract = async () => {
  const {ok, data} = await send('POST',
    '/evidence/decision-contract/validate', {
      decision_type: $('ev-decision').value,
      case_id: $('ev-case').value,
      evidence_ids: EV_SELECTED,
      user_intent_reference: $('ev-intent').value || null,
      would_action_survive_without_untrusted_text:
        !$('ev-doc-caused').checked});
  if (!ok) { evmsg('Refused: ' + data.detail, false); return; }
  const steps = [
    ['tenant/case scope', data.hard_blockers.some(b =>
      b.includes('mismatch')) ? 'FAILED' : 'ok'],
    ['integrity + lifecycle state', data.rejected.length
      ? data.rejected.length + ' evidence object(s) rejected' : 'ok'],
    ['admissibility', data.admissible.length + ' admissible'],
    ['requirement profile', data.hard_blockers.filter(b =>
      !b.includes('mismatch')).map(esc).join('; ') || 'ok'],
    ['causal action guard', data.causality.decision + ' — ' +
      data.causality.reasons.map(esc).join('; ')],
    ['final', data.final]];
  $('ev-contract').innerHTML = `<p>Final:
    <b class="${data.final === 'ALLOWED' ? 'ok' : 'err'}">${data.final}
    </b> · contract <code>${data.contract_id.slice(0, 8)}</code> ·
    case completed by this: <b>false</b></p>
    <p><b>Decision replay (UI display of server results — the API
    decided):</b></p>
    <ol>${steps.map(([k, v]) => `<li>${k}: ${v}</li>`).join('')}</ol>
    ${data.final !== 'ALLOWED' ? `<p><b>Hard Blocker Proof:</b>
      ${data.hard_blockers.map(b => `${esc(b)} —
        <i>${blockerHelp(b)}</i>`).join('<br>') ||
      '<i>blocked by causal guard, not by evidence</i>'}<br>
      Scores cannot override this. hard blockers override scores.</p>`
      : ''}`;
};
"""

CRM_SECTIONS = """
<section id="crm-section"><h2>Customer Panel</h2>
<p><b>Finalis is the source of operational truth for case outcomes.</b>
Customer truth is verified, not guessed — AI can suggest, human
verification decides.</p>
<p><small><b>Case outcome fields are owned by Finalis</b> and cannot be
synced externally. External CRM providers (HubSpot / Salesforce /
Pipedrive / Zoho / Odoo / SuiteCRM / Twenty) are <b>not connected</b>;
the NullCrmAdapter is a scaffold/dry-run only (SCAFFOLDED_ONLY), OAuth
is not implemented, webhook ingestion is not implemented, sync is
dry-run/decision only and <b>no external provider is called</b>.
Marketing consent is never implied. Merge is human-only. Cross-tenant
relationships are impossible. <b>Production readiness is false.</b>
</small></p>
<div class="cards" id="crm-dashboard"></div>
<div id="crm-create" hidden>
  <input id="crm-name" placeholder="display name" style="max-width:14rem"/>
  <select id="crm-kind"><option>person</option><option>organization</option>
  </select>
  <input id="crm-email" placeholder="email" style="max-width:12rem"/>
  <input id="crm-phone" placeholder="phone" style="max-width:10rem"/>
  <button id="crm-create-btn" onclick="crmCreateParty()">Create
    customer</button>
</div>
<div id="crm-msg"></div>
<div id="crm-caseparties"></div>
<h3>Customers</h3><div id="crm-list"><i>Loading customers…</i></div>
<div id="crm-detail"></div>
</section>
"""

CRM_JS = """
const canCrmWrite = () => ME && ME.permissions.includes('case.update');
const canVerifyMemory = () => ME &&
  ME.permissions.includes('action.approve');
const canMerge = () => ME &&
  ME.permissions.includes('tenant.manage_users');
const canSync = () => ME &&
  ME.permissions.includes('tenant.manage_integrations');
const cmsg = (t, ok) => { $('crm-msg').innerHTML =
  `<span class="${ok ? 'ok' : 'err'}">${esc(t)}</span>`; };

window.loadCrmSection = async (me, cases) => {
  $('crm-create').hidden = !canCrmWrite();
  window.CRM_CASES = cases;
  await loadParties();
};

window.loadParties = async () => {
  const data = await get('/crm/parties');
  const parties = data.parties.filter(p => !p.merged_into_id);
  const kinds = {};
  parties.forEach(p => kinds[p.kind] = (kinds[p.kind] || 0) + 1);
  $('crm-dashboard').innerHTML = [
    ['customers', parties.length], ['persons', kinds.person || 0],
    ['organizations', kinds.organization || 0],
    ['legacy case contacts', data.legacy_case_contacts.length]]
    .map(([k, v]) => `<div class="card"><b>${v}</b><span>${k}</span>
      </div>`).join('');
  $('crm-list').innerHTML = parties.length ?
    '<table><tr><th>Name</th><th>Type</th><th></th></tr>' +
    parties.map(p => `<tr data-party="${p.id}">
      <td>${esc(p.display_name)}</td><td>${p.kind}</td>
      <td><button onclick="openParty('${p.id}')">Open</button></td>
      </tr>`).join('') + '</table>' :
    '<i>No customers yet.</i>';
};

window.crmCreateParty = async () => {
  const cps = [];
  if ($('crm-email').value) cps.push({kind: 'EMAIL',
                                      value: $('crm-email').value});
  if ($('crm-phone').value) cps.push({kind: 'MOBILE',
                                      value: $('crm-phone').value});
  const {ok, data} = await send('POST', '/crm/parties', {
    kind: $('crm-kind').value, display_name: $('crm-name').value,
    contact_points: cps});
  cmsg(ok ? 'Customer created.' : 'Refused: ' + data.detail, ok);
  if (ok) { await loadParties(); openParty(data.id); }
};

window.crmFor = async (caseId) => {
  const rows = await get(`/crm/cases/${caseId}/parties`);
  $('crm-caseparties').innerHTML = '<p><b>Parties on the selected case:'
    + '</b> ' + (rows.length ? rows.map(r =>
      `${esc(r.display_name)} (${esc(r.role)})
       <button onclick="openParty('${r.party_id}')">Open</button>`)
      .join(' · ') : '<i>none linked yet</i>') + '</p>';
  $('crm-section').scrollIntoView();
};

function customerReadiness(detail, consents, memory, dedupe) {
  // NON-AUTHORITATIVE UI SUMMARY — server decisions remain authoritative.
  if (memory.some(m => m.memory_type === 'DISPUTED_FACT'))
    return {value: 0, note: 'disputed fact present — automation blocked ' +
            'until a human resolves it'};
  const denied = consents.filter(c => ['DENIED', 'REVOKED']
    .includes(c.status)).length;
  const consentReadiness = consents.length
    ? 1 - denied / consents.length : 0.5;
  const verified = memory.filter(m =>
    m.memory_type === 'VERIFIED_FACT').length;
  const memoryCoverage = memory.length ? verified / memory.length : 0.5;
  const dupSafety = dedupe.length ? 0.3 : 1;
  const promiseHealth = detail.open_promises.length > 3 ? 0.5 : 1;
  const reachability = detail.contact_points.length ? 1 : 0;
  const value = 0.30 * consentReadiness + 0.25 * memoryCoverage
    + 0.20 * dupSafety + 0.15 * promiseHealth + 0.10 * reachability;
  return {value: Math.round(value * 100) / 100, note: ''};
}

window.openParty = async (id) => {
  const d = await get('/crm/parties/' + id);
  const consents = await get(`/crm/parties/${id}/consents`);
  const promises = await get(`/crm/parties/${id}/promises`);
  const memory = await get(`/crm/parties/${id}/memory`);
  const dedupe = await get(`/crm/parties/${id}/dedupe-candidates`);
  const refs = await get(`/crm/parties/${id}/external-references`);
  const rels = await get(`/crm/parties/${id}/relationships`);
  const w = canCrmWrite();
  const ready = customerReadiness(d, consents, memory, dedupe);
  const groups = {VERIFIED_FACT: [], AI_SUGGESTED: [], DISPUTED_FACT: [],
                  STALE_FACT: [], other: []};
  memory.forEach(m => (groups[m.memory_type] || groups.other).push(m));
  const memRow = (m) => `<li>${esc(JSON.stringify(m.content))}
    <small>source ${esc(m.source)} · confidence ${m.confidence}
    ${m.sensitive ? ' · SENSITIVE' : ''}</small>
    ${w && m.memory_type === 'AI_SUGGESTED' && canVerifyMemory()
      ? `<button onclick="memAct('${m.id}','verify','${id}')">verify as
         human</button>` : ''}
    ${w ? `<button onclick="memAct('${m.id}','dispute','${id}')">dispute
      </button>
      <button onclick="memAct('${m.id}','mark-stale','${id}')">mark stale
      </button>` : ''}</li>`;
  const consentRow = (c) => `<li>${c.channel}: <b>${c.status}</b>
    <small>${esc(c.source)}</small></li>`;
  const promiseRow = (p) => {
    const overdue = p.due_at && p.status === 'open'
      && new Date(p.due_at) < new Date();
    return `<li${overdue ? ' class="err"' : ''}>${esc(p.what)}
      <small>${p.status}${p.due_at ? ' · due ' + p.due_at.slice(0, 16)
        : ''}${overdue ? ' · OVERDUE' : ''}
      ${p.case_id ? ' · case ' + esc(p.case_id.slice(0, 8)) : ''}
      </small></li>`;
  };
  $('crm-detail').innerHTML = `
    <h3>${esc(d.display_name)} <span class="badge">${d.kind}</span></h3>
    <p id="crm-readiness"><b>Customer Readiness Index
      (NON-AUTHORITATIVE UI SUMMARY — server-side policy remains the
      source of truth):</b> ${ready.value}
      ${ready.note ? `<b class="err">${esc(ready.note)}</b>` : ''}</p>

    <h4>Contact points</h4>
    <ul>${d.contact_points.map(c => `<li>${c.kind}:
      ${esc(c.value)}${c.preferred ? ' (preferred)' : ''}</li>`).join('')
      || '<li><i>none</i></li>'}</ul>
    ${w ? `<p><select id="cp-kind"><option>EMAIL</option>
      <option>MOBILE</option><option>WHATSAPP</option></select>
      <input id="cp-value" placeholder="value" style="max-width:12rem"/>
      <button onclick="addContact('${id}')">Add contact</button>
      <small>(editing an existing contact point is MISSING — future
      API)</small></p>` : ''}

    <h4>Consent Center</h4>
    <p><small>Marketing consent is never implied. Revoked or denied
    consent cannot be overridden by AI. Unknown marketing consent
    requires human review. Service communication depends on tenant
    policy.</small></p>
    <ul>${consents.map(consentRow).join('')
      || '<li><i>no consent recorded (UNKNOWN)</i></li>'}</ul>
    ${w ? `<p><select id="consent-channel"><option>EMAIL</option>
      <option>SMS</option><option>WHATSAPP</option>
      <option>PHONE_CALL</option><option>MARKETING</option>
      <option>SERVICE_UPDATES</option></select>
      <select id="consent-status"><option>GRANTED</option>
      <option>DENIED</option><option>REVOKED</option></select>
      <button onclick="recordConsent('${id}')">Record consent</button>
      </p>` : ''}
    <p><select id="check-channel"><option>EMAIL</option>
      <option>SMS</option><option>WHATSAPP</option>
      <option>PHONE_CALL</option></select>
      <select id="check-purpose"><option>service</option>
      <option>marketing</option></select>
      <button id="consent-check-btn" onclick="checkConsent('${id}')">
      Check before outreach</button></p>
    <div id="consent-explain"></div>

    <h4>Promises <small>(operational commitments)</small></h4>
    <p><b>Customer promised Finalis:</b></p>
    <ul>${promises.filter(p => p.promisor === 'customer').map(promiseRow)
      .join('') || '<li><i>none</i></li>'}</ul>
    <p><b>Finalis promised the customer:</b></p>
    <ul>${promises.filter(p => p.promisor === 'finalis').map(promiseRow)
      .join('') || '<li><i>none</i></li>'}</ul>
    ${w ? `<p><select id="promise-by"><option>customer</option>
      <option>finalis</option></select>
      <input id="promise-what" placeholder="what was promised"
        style="max-width:16rem"/>
      <input id="promise-due" type="datetime-local"
        style="max-width:13rem"/>
      <button onclick="addPromise('${id}')">Record promise</button></p>`
      : ''}

    <h4>Customer memory</h4>
    <p><small>AI-suggested memory is not a verified fact. Only a human
    can verify memory. Disputed facts block automation. Stale facts
    cannot drive critical decisions alone. Sensitive memory requires
    permission. <b>AI can suggest. Human verification decides.</b>
    </small></p>
    <p><b class="ok">Verified facts:</b></p>
    <ul>${groups.VERIFIED_FACT.map(memRow).join('')
      || '<li><i>none</i></li>'}</ul>
    <p><b class="err">AI-suggested (lower trust — not verified):</b></p>
    <ul style="opacity:.7">${groups.AI_SUGGESTED.map(memRow).join('')
      || '<li><i>none</i></li>'}</ul>
    <p><b>Disputed:</b></p>
    <ul>${groups.DISPUTED_FACT.map(memRow).join('')
      || '<li><i>none</i></li>'}</ul>
    <p><b>Stale:</b></p>
    <ul>${groups.STALE_FACT.map(memRow).join('')
      || '<li><i>none</i></li>'}</ul>
    ${w ? `<p><input id="mem-key" placeholder="fact key"
        style="max-width:9rem"/>
      <input id="mem-value" placeholder="value" style="max-width:11rem"/>
      <select id="mem-source"><option>human</option>
      <option>ai_worker</option></select>
      <button onclick="addMemory('${id}')">Add memory</button></p>` : ''}

    <h4>Case relationships</h4>
    <ul>${rels.map(r => `<li>${r.to_kind}: ${esc(r.to_id.slice(0, 8))}
      (${esc(r.role)})</li>`).join('') || '<li><i>none</i></li>'}</ul>
    ${w ? `<p><select id="rel-case">${(window.CRM_CASES || []).map(c =>
      `<option value="${c.id}">${esc(c.title)}</option>`).join('')}
      </select>
      <button onclick="linkCase('${id}')">Link to case</button></p>` : ''}

    <h4>Duplicates / merge</h4>
    <p><small>Merge is human-only. <b>AI may suggest candidates but
    cannot approve merge.</b> Cross-tenant duplicates can never merge.
    Conflicting verified facts require review. History is preserved —
    the merged party is tombstoned, not deleted.</small></p>
    <div id="crm-dedupe">${dedupe.length ? dedupe.map(c =>
      `<div class="card"><b>${c.verdict}</b> score ${c.score}<br>
       <small>${c.signals.map(esc).join('; ')}</small><br>
       ${canMerge() ? `<button onclick="crmMerge('${id}',
         '${c.party_id}')">Merge into this customer…</button>` : ''}
       </div>`).join('') : '<i>No duplicate candidates.</i>'}</div>

    <h4>External CRM (dry-run only)</h4>
    <p><small>External CRM is not connected in production. Dry-run only
    unless a provider is explicitly configured. External CRM cannot
    overwrite verified Finalis data. No external provider is
    called.</small></p>
    <ul>${refs.map(r => `<li>${esc(r.provider)} / ${esc(r.object_kind)}
      / ${esc(r.external_id)}</li>`).join('')
      || '<li><i>no external references</i></li>'}</ul>
    ${canSync() ? `<p>
      <input id="ref-provider" placeholder="provider (e.g. hubspot)"
        style="max-width:10rem"/>
      <input id="ref-id" placeholder="external id"
        style="max-width:8rem"/>
      <button onclick="addExtRef('${id}')">Add reference</button></p>
      <p><input id="sync-field" value="email" style="max-width:8rem"/>
      <input id="sync-internal" placeholder="internal value"
        style="max-width:10rem"/>
      <input id="sync-external" placeholder="external value"
        style="max-width:10rem"/>
      <label><input type="checkbox" id="sync-verified"/> internal value
      is human-verified</label>
      <button id="sync-dryrun-btn" onclick="syncDryRun()">Sync
        dry-run</button>
      <button onclick="syncDecisionRun()">Sync decision</button></p>`
      : ''}
    <div id="sync-explain"></div>`;
};

window.addContact = async (id) => {
  const {ok, data} = await send('POST', `/crm/parties/${id}/contacts`,
    {kind: $('cp-kind').value, value: $('cp-value').value});
  cmsg(ok ? 'Contact added (normalized to ' + data.value + ').'
          : 'Refused: ' + data.detail, ok);
  if (ok) openParty(id);
};

window.recordConsent = async (id) => {
  const {ok, data} = await send('POST', `/crm/parties/${id}/consents`,
    {channel: $('consent-channel').value,
     status: $('consent-status').value, source: 'portal'});
  cmsg(ok ? 'Consent recorded.' : 'Refused: ' + data.detail, ok);
  if (ok) openParty(id);
};

window.checkConsent = async (id) => {
  const channel = $('check-channel').value;
  const purpose = $('check-purpose').value;
  const {ok, data} = await send('POST', '/crm/consent/check',
    {party_id: id, channel, purpose});
  if (!ok) { cmsg('Refused: ' + data.detail, false); return; }
  const result = data.allowed ? 'ALLOWED'
    : (data.requires_review ? 'HUMAN_REVIEW' : 'BLOCKED');
  $('consent-explain').innerHTML = `<p><b>Consent decision:</b>
    channel ${channel} · purpose ${purpose} →
    <b class="${data.allowed ? 'ok' : 'err'}">${result}</b><br>
    <small>${data.reasons.map(esc).join('; ')}</small></p>`;
};

window.addPromise = async (id) => {
  const body = {promisor: $('promise-by').value,
                what: $('promise-what').value};
  if ($('promise-due').value)
    body.due_at = $('promise-due').value + ':00';
  const {ok, data} = await send('POST', `/crm/parties/${id}/promises`,
                                body);
  cmsg(ok ? 'Promise recorded.' : 'Refused: ' + data.detail, ok);
  if (ok) openParty(id);
};

window.addMemory = async (id) => {
  const content = {};
  content[$('mem-key').value || 'note'] = $('mem-value').value;
  const {ok, data} = await send('POST', `/crm/parties/${id}/memory`,
    {memory_type: 'VERIFIED_FACT', content,
     source: $('mem-source').value, confidence: 0.9});
  if (ok && data.memory_type === 'AI_SUGGESTED') {
    cmsg('Stored as AI_SUGGESTED — AI-suggested memory is not a ' +
         'verified fact until a human verifies it.', true);
  } else {
    cmsg(ok ? 'Memory added.' : 'Refused: ' + data.detail, ok);
  }
  if (ok) openParty(id);
};

window.memAct = async (memId, action, partyId) => {
  const {ok, data} = await send('POST', `/crm/memory/${memId}/${action}`,
                                {});
  cmsg(ok ? action + ' → ' + data.memory_type
          : 'Refused: ' + data.detail, ok);
  openParty(partyId);
};

window.linkCase = async (id) => {
  const {ok, data} = await send('POST', '/crm/relationships',
    {from_id: id, to_id: $('rel-case').value, to_kind: 'case',
     role: 'customer'});
  cmsg(ok ? 'Linked to case.' : 'Refused: ' + data.detail, ok);
  if (ok) openParty(id);
};

window.crmMerge = async (survivingId, mergedId) => {
  const reason = prompt('Merge reason (required — merge is human-only)');
  if (reason === null) return;
  const {ok, data} = await send('POST', '/crm/merge',
    {surviving_party_id: survivingId, merged_party_id: mergedId,
     reason});
  cmsg(ok ? 'Merged. History preserved (tombstoned).'
          : 'Refused: ' + data.detail, ok);
  await loadParties();
  openParty(survivingId);
};

window.addExtRef = async (id) => {
  const {ok, data} = await send('POST',
    `/crm/parties/${id}/external-references`,
    {provider: $('ref-provider').value, object_kind: 'Contact',
     external_id: $('ref-id').value});
  cmsg(ok ? 'External reference mapped (reference only — not core '
        + 'identity).' : 'Refused: ' + data.detail, ok);
  if (ok) openParty(id);
};

window.syncDryRun = async () => {
  const {ok, data} = await send('POST', '/crm/sync/dry-run',
    {field: $('sync-field').value,
     internal_value: $('sync-internal').value,
     external_value: $('sync-external').value,
     internal_verified: $('sync-verified').checked});
  if (!ok) { cmsg('Refused: ' + data.detail, false); return; }
  $('sync-explain').innerHTML = `<p><b>Dry-run:</b>
    <b>${data.decision}</b> — ${data.reasons.map(esc).join('; ')}<br>
    idempotency key <code>${data.idempotency_key.slice(0, 12)}…</code> ·
    external write happened: <b>${data.external_write_happened}</b>
    (adapter: ${esc(data.adapter.provider || 'null-crm')}, mock)</p>`;
};

window.syncDecisionRun = async () => {
  const {ok, data} = await send('POST', '/crm/sync/decision',
    {direction: 'import', field: $('sync-field').value,
     internal_value: $('sync-internal').value,
     external_value: $('sync-external').value,
     internal_verified: $('sync-verified').checked,
     internal_changed: true, external_changed: true});
  if (!ok) { cmsg('Refused: ' + data.detail, false); return; }
  $('sync-explain').innerHTML = `<p><b>Sync decision:</b>
    <b>${data.decision}</b> — ${data.reasons.map(esc).join('; ')}
    ${data.conflict ? `<br><small>conflict on
      '${esc(data.conflict.field)}': internal
      '${esc(data.conflict.internal_value)}' vs external
      '${esc(data.conflict.external_value)}' →
      ${esc(data.conflict.resolution)}</small>` : ''}</p>`;
};
"""

# ===========================================================================
# V-F — Evidence Proof Workbench. A case-first, evidence-first, audit-ready
# verification workbench over the tested Evidence V-A..V-E APIs. The UI
# EXPLAINS proof status (Merkle inclusion, append-only consistency, proof
# algebra, verdict lattice, verification state machine, derivative chain,
# conflict matrix); server-side Evidence logic stays authoritative. Panels
# with no server API are labeled honestly (MISSING / NOT_EXPOSED), never
# faked. Every mandated honesty sentence lives in the static section below
# so it is present in the served page regardless of JS execution.
# ===========================================================================
WORKBENCH_SECTIONS = """
<section id="workbench-section"><h2>Evidence Proof Workbench</h2>
<p><small><b>Finalis is evidence-first and case-first.</b> This workbench
explains cryptographic proof status; <b>server-side Evidence verification
remains authoritative</b> — a display score cannot unlock actions.
<b>Integrity verification and business truth are separate verdicts.</b>
<b>Cryptographic integrity is not the same as legal validity.</b>
UI explanations are not legal advice. <b>Production readiness is false.</b>
</small></p>

<h3>Evidence Proof Dashboard</h3>
<p><small id="wb-dash-note"><b>NON-AUTHORITATIVE UI SUMMARY — server-side
Evidence verification remains the source of truth.</b> Counts are computed
in the browser from list/detail APIs and never hide raw status or
warnings.</small></p>
<div class="cards" id="wb-dashboard"><i>Loading proof dashboard…</i></div>
<div id="wb-msg"></div>

<h3>Evidence List</h3>
<p><small>Rows come only from <code>/evidence</code> (real API, tenant-scoped,
permission-gated). No fake evidence rows.</small></p>
<div id="wb-list"><i>Loading evidence…</i></div>

<div id="wb-detail">
<p><i>Select an evidence item to open its proof workbench.</i></p>

<div class="wb-panel" id="wb-p-detail" hidden>
  <h3>Evidence Detail</h3>
  <p><small>Metadata is escaped before render. Never shown: secrets,
  credentials, tokens, private keys, unsafe paths, cross-tenant data.</small></p>
  <div id="wb-detail-body"></div>
</div>

<div class="wb-panel" id="wb-p-inclusion" hidden>
  <h3>Merkle Inclusion Proof</h3>
  <p><small><b>Merkle proof explains inclusion. It does not explain business
  truth.</b> <b>Hash match proves byte-level consistency, not customer
  intent.</b> Server-side Evidence verification remains authoritative; UI
  recomputation, if shown, is explanatory only. RFC 9162 inclusion-proof
  terminology (leaf, proof path, tree size, root).</small></p>
  <div id="wb-inclusion-body"></div>
</div>

<div class="wb-panel" id="wb-p-consistency" hidden>
  <h3>Merkle Consistency / Append-Only</h3>
  <p><small><b>Inclusion proof shows that one item is in a tree. Consistency
  proof shows whether the log evolved append-only.</b> Append-only evidence
  cannot be assumed unless the server exposes and verifies consistency data
  (RFC 9162). The Finalis Evidence Transparency Log now exposes a
  server-verified consistency proof between root checkpoints
  (<code>/evidence/merkle-roots/{id}/consistency</code>);
  <b>Merkle consistency proves append-only tree evolution only; it does not
  prove legal validity.</b> Server-side Evidence verification remains
  authoritative; UI explanation cannot unlock actions.</small></p>
  <p><small><b>Status legend:</b> VERIFIED → “Merkle consistency proof is
  server-verified.” · NOT_VERIFIED → “Append-only consistency is not
  verified.” · PROOF_MISSING → “Historical leaf order was not stored, so
  consistency proof cannot be reconstructed.” · INVALID_RANGE → previous
  tree size exceeds current tree size.</small></p>
  <p><small><b>Transparency checkpoint (future-ready slots):</b> Checkpoint
  signatures are not implemented. Witness cosignatures are not implemented.
  SCITT receipts are not implemented. No external transparency service is
  called.</small></p>
  <div id="wb-consistency-body"></div>
</div>

<div class="wb-panel" id="wb-p-algebra" hidden>
  <h3>Proof Algebra / Verdict</h3>
  <p><small><b>Positive signals cannot average away a critical proof
  failure.</b> Hard-fail dimensions force a non-verified verdict, readiness
  0 and automation off; a display score cannot override the verdict.
  Server decisions remain authoritative.</small></p>
  <div id="wb-algebra-body"></div>
</div>

<div class="wb-panel" id="wb-p-state" hidden>
  <h3>Verification State Machine</h3>
  <p><small><b>Verification state is server-authoritative. UI state
  explanation cannot unlock actions. Failed proof blocks automation.</b>
  </small></p>
  <div id="wb-state-body"></div>
</div>

<div class="wb-panel" id="wb-p-derivative" hidden>
  <h3>Derivative Evidence Chain</h3>
  <p><small><b>Derivative evidence must preserve parent linkage. A
  derivative is not stronger than its parent evidence.</b> Redaction creates
  a new derivative; it must not overwrite the original. Missing parent
  evidence blocks derivative trust. OCR-derived text is displayed only if it
  already exists — the <b>OCR router is not part of V-F</b>
  (SCAFFOLDED_ONLY).</small></p>
  <div id="wb-derivative-body"></div>
</div>

<div class="wb-panel" id="wb-p-contract" hidden>
  <h3>Contract History / Decision Evidence</h3>
  <p><small><b>Contract history is append-oriented.</b> Evidence can support
  a contract event, but the UI cannot rewrite contract truth.
  <b>Payment/quote acceptance wiring is not part of V-F.</b></small></p>
  <div id="wb-contract-body"></div>
</div>

<div class="wb-panel" id="wb-p-provenance" hidden>
  <h3>Provenance / C2PA Signal</h3>
  <p><small><b>Provenance is a signal, not final truth. C2PA provenance is
  not final truth</b> and does not automatically prove legal validity;
  provenance conflicts require review. Finalis Evidence verification remains
  authoritative. No provenance/C2PA API is exposed by the server —
  classified <b>MISSING</b>; no C2PA data is faked.</small></p>
  <div id="wb-provenance-body"></div>
</div>

<div class="wb-panel" id="wb-p-timestamp" hidden>
  <h3>Timestamp / Evidence Record</h3>
  <p><small><b>Timestamping proves existence at a time; it does not prove
  business truth.</b> Expired or missing timestamp evidence requires review;
  long-term evidence renewal is a separate production capability.
  <b>RFC 3161 timestamp provider is not connected unless explicitly
  configured. RFC 4998 evidence record renewal is not implemented unless
  server exposes it.</b> No timestamp API is exposed — classified
  <b>MISSING</b>.</small></p>
  <div id="wb-timestamp-body"></div>
</div>

<div class="wb-panel" id="wb-p-scitt" hidden>
  <h3>SCITT / Statement Receipt Readiness</h3>
  <p><small><b>SCITT statement/receipt integration is not implemented.</b>
  SCITT readiness is a future-compatible slot only (RFC 9943). SCITT can
  support transparent statements, but Finalis remains the evidence
  authority; <b>SCITT receipt presence does not equal business truth.</b>
  No external transparency service is called in V-F. Classified
  <b>MISSING</b>.</small></p>
  <div id="wb-scitt-body"></div>
</div>

<div class="wb-panel" id="wb-p-crypto" hidden>
  <h3>Cryptographic Agility / PQC Readiness</h3>
  <p><small>Algorithm agility is required for long-term evidence.
  <b>Unknown or deprecated algorithms require review.</b> PQC readiness is
  informational unless server verification enforces it.
  <b>Post-quantum cryptography is not implemented in V-F</b> (NIST FIPS
  203/204/205 awareness only).</small></p>
  <div id="wb-crypto-body"></div>
</div>

<div class="wb-panel" id="wb-p-conflict" hidden>
  <h3>Evidence Conflict Matrix</h3>
  <p><small><b>Cryptographic integrity is not the same as legal validity.
  Provenance is not the same as integrity. A valid timestamp is not the same
  as a valid business claim. A receipt is not the same as business truth.
  Hash mismatch blocks automation.</b></small></p>
  <div id="wb-conflict-body"></div>
</div>

<div class="wb-panel" id="wb-p-report" hidden>
  <h3>Proof Explanation / Human Report</h3>
  <p><small><b>UI explanations are not legal advice.</b> Evidence
  verification does not automatically approve a case outcome; missing proof
  data requires review; <b>hash mismatch blocks automation.</b> A signed
  verification report export is <b>MISSING</b>.</small></p>
  <div id="wb-report-body"></div>
</div>

<div class="wb-panel" id="wb-p-graph" hidden>
  <h3>Evidence Chain Graph / Relationship</h3>
  <p><small>Case → evidence → derivative → contract event → proof root →
  timestamp/provenance/SCITT slots → algorithm metadata → warning. Simple
  indented relationship view — explainability, not decoration.</small></p>
  <div id="wb-graph-body"></div>
</div>
</div>

<div class="wb-panel" id="wb-p-report-artifact" hidden>
  <h3>Proof Report Package</h3>
  <p><small>A canonical, replayable proof-report artifact
  (<code>/evidence/{id}/proof-reports</code>). <b>Report hash is
  implemented.</b> <b>Report signing requires configured signing
  infrastructure.</b> <b>Safe view is not a separate proof.</b>
  <b>UI report display is not legal advice.</b> Cryptographic verification
  is not the same as legal validity. <b>Server-side Evidence logic remains
  authoritative</b> — a display score cannot unlock actions. Fields:
  report_id · report_hash · package_hash · canonicalization_version ·
  report_hash_input_schema_version · report_signature_status ·
  signature_envelope_type · redaction_profile · replay_status ·
  generated_at · final_technical_verdict.</small></p>
  <div id="wb-report-artifact-body"></div>
</div>

<h3>Production Honesty</h3>
<div id="wb-p-honesty"><ul>
  <li><b>Production readiness is false.</b></li>
  <li>External notarization is not connected.</li>
  <li>Blockchain anchoring is not implemented.</li>
  <li>RFC 3161 timestamp provider is not connected unless explicitly
    configured.</li>
  <li>RFC 4998 evidence record renewal is not implemented unless server
    exposes it.</li>
  <li>C2PA provenance is not final truth.</li>
  <li>SCITT statement/receipt integration is not implemented.</li>
  <li>Sigstore/Rekor integration is not implemented.</li>
  <li>Post-quantum cryptography is not implemented in V-F.</li>
  <li>MinIO Object Lock adapter is not implemented unless explicitly added
    in a later mission.</li>
  <li>OCR router is not part of V-F.</li>
  <li>Payment/quote acceptance wiring is not part of V-F.</li>
  <li>UI explanations are not legal advice.</li>
  <li>Server-side Evidence logic remains authoritative.</li>
</ul></div>
</section>
"""

WORKBENCH_JS = """
// --- V-F Evidence Proof Workbench (reuses global esc/$/get/send/ME) -------
const wbMsg = (t, ok) => { $('wb-msg').innerHTML =
  `<span class="${ok ? 'ok' : 'err'}">${esc(t)}</span>`; };
const wbCanAudit = () => ME && ME.permissions.includes('audit.view');
const wbCanAnalyze = () => ME && ME.permissions.includes('document.analyze');
// A GET that degrades to null instead of throwing (used for role-gated
// proof/contract/ledger endpoints so a viewer never breaks the section).
const wbTry = async (p) => { try { return await get(p); }
  catch (e) { return null; } };

window.loadWorkbenchSection = async (me, cases) => {
  window.WB_CASES = cases;
  await wbLoadList();
};

window.wbLoadList = async (caseId) => {
  const rows = await get('/evidence' + (caseId ? '?case_id=' + caseId : ''));
  window.WB_ROWS = rows;
  const ledger = wbCanAudit() ? (await wbTry('/evidence/merkle-roots')) : null;
  // NON-AUTHORITATIVE UI summary from the list; raw state stays visible.
  const by = {}; rows.forEach(r => by[r.state] = (by[r.state] || 0) + 1);
  const verified = by.ADMISSIBLE || 0;
  const pending = (by.QUARANTINED || 0) + (by.SCANNED_CLEAN || 0);
  const failed = (by.REJECTED || 0);
  const cards = [
    ['evidence items', rows.length],
    ['admissible (integrity path)', verified],
    ['pending verification', pending],
    ['rejected / failed', failed],
    ['linked to a case', rows.filter(r => r.case_id).length],
    ['Merkle roots in ledger', ledger ? ledger.length : 'audit.view only'],
    ['provenance signal', 'MISSING (no API)'],
    ['timestamp signal', 'MISSING (no API)'],
    ['SCITT statement/receipt', 'MISSING (no API)'],
    ['PQC-ready crypto', 'NOT_EXPOSED'],
    ['classical-only crypto', 'sha-256 (informational)']];
  $('wb-dashboard').innerHTML = cards.map(([k, v]) =>
    `<div class="card"><b>${esc(String(v))}</b><span>${esc(k)}</span></div>`)
    .join('');
  $('wb-list').innerHTML = rows.length ?
    '<table><tr><th>Evidence</th><th>Case</th><th>Type</th>' +
    '<th>Server state</th><th>Sensitivity</th><th></th></tr>' +
    rows.map(r => `<tr data-ev="${esc(r.id)}">
      <td><small>${esc(r.id.slice(0, 8))}</small> ${esc(
        r.original_filename || '')}</td>
      <td><small>${esc((r.case_id || '').slice(0, 8))}</small></td>
      <td>${esc(r.evidence_type)}</td><td>${esc(r.state)}</td>
      <td>${esc(r.sensitivity)}</td>
      <td><button onclick="wbOpen('${esc(r.id)}')">Open proof</button></td>
      </tr>`).join('') + '</table>' :
    '<i>No evidence yet.</i>';
};

// ---- Proof algebra (Finalis IP; NON-AUTHORITATIVE UI computation) --------
// D1 HashIntegrity D2 MerkleInclusion D3 MerkleConsistency D4 Timestamp
// D5 Provenance D6 DerivativeChain D7 ContractLink D8 TenantIsolation
// D9 AlgorithmAgility D10 Freshness D11 BusinessContext.
window.wbProofAlgebra = (d, proof, derivs, contracts, consistency) => {
  const dims = {};
  // D1 — hash integrity (server-computed).
  dims.D1 = d.integrity ? (d.integrity.valid ? 'PASS' : 'FAIL') : 'UNKNOWN';
  // D2 — Merkle inclusion (server proof.verifies; root vs stored root).
  dims.D2 = proof == null ? 'NOT_EXPOSED'
    : (proof.verifies && proof.root ? 'PASS' : 'FAIL');
  // D3 — append-only consistency: only VERIFIED if the server verified it.
  dims.D3 = consistency == null ? 'NOT_EXPOSED'
    : (consistency.ok ? 'PASS' : 'FAIL');
  // D4/D5 — no server API.
  dims.D4 = 'NOT_EXPOSED'; dims.D5 = 'NOT_EXPOSED';
  // D6 — derivative chain: every derivative must link to a present parent
  // and cannot claim more trust than the (this) parent.
  if (derivs == null) dims.D6 = 'NOT_EXPOSED';
  else if (!derivs.length) dims.D6 = 'NOT_APPLICABLE';
  else {
    const parentVerified = dims.D1 === 'PASS';
    const overTrust = derivs.some(x =>
      (x.confidence != null) && !parentVerified && x.confidence >= 0.99);
    const orphan = derivs.some(x => x.parent_evidence_id
      && x.parent_evidence_id !== d.id);
    dims.D6 = (overTrust || orphan) ? 'FAIL' : 'PASS';
  }
  // D7 — contract link (informational unless a contract requires it).
  dims.D7 = contracts == null ? 'NOT_EXPOSED'
    : (contracts.length ? 'PASS' : 'NOT_APPLICABLE');
  // D8 — tenant isolation: detail loaded => server confirmed same tenant.
  dims.D8 = 'PASS';
  // D9 — algorithm agility (informational; sha-256 = classical, supported).
  const alg = (d.integrity && d.integrity.algorithm || '').toLowerCase();
  dims.D9 = !alg ? 'UNKNOWN'
    : (/(md5|sha1|sha-1)/.test(alg) ? 'UNSUPPORTED_CRITICAL_ALGORITHM'
      : 'PASS');
  // D10 — freshness (soft; last integrity check known?).
  dims.D10 = d.integrity && d.integrity.valid ? 'PASS' : 'UNKNOWN';
  // D11 — business context (server state). Disputed/rejected is hard.
  dims.D11 = ['REJECTED', 'DISPUTED'].includes(d.state) ? 'DISPUTED'
    : (d.state === 'ADMISSIBLE' && d.human_verified ? 'PASS'
      : 'REVIEW_REQUIRED');
  return dims;
};

// Verdict lattice — a stronger verdict only if every lower proof holds.
window.wbVerdict = (dims) => {
  const zero = (verdict, why) => ({verdict, readiness: 0,
    automation_allowed: false, hard_fail: true, why});
  if (dims.D1 === 'FAIL')
    return zero('TAMPER_WARNING', 'hash mismatch — byte-level integrity failed');
  if (dims.D2 === 'FAIL')
    return zero('FAILED_VERIFICATION', 'Merkle root/inclusion mismatch');
  if (dims.D8 === 'FAIL')
    return zero('FAILED_VERIFICATION', 'tenant isolation breach');
  if (dims.D6 === 'FAIL')
    return zero('REVIEW_REQUIRED', 'derivative parent missing or over-trusted');
  if (dims.D3 === 'FAIL')
    return zero('REVIEW_REQUIRED', 'append-only consistency failed');
  if (dims.D9 === 'UNSUPPORTED_CRITICAL_ALGORITHM')
    return zero('REVIEW_REQUIRED', 'unsupported/deprecated critical algorithm');
  if (dims.D11 === 'DISPUTED')
    return zero('REVIEW_REQUIRED', 'business context is disputed');
  // No hard fail below this line — compute a display-only score.
  const score = wbReadiness(dims);
  if (dims.D1 !== 'PASS')
    return {verdict: 'NOT_VERIFIED', readiness: score,
      automation_allowed: false, hard_fail: false,
      why: 'hash integrity not yet verified by the server'};
  if (dims.D2 !== 'PASS')
    return {verdict: 'REVIEW_REQUIRED', readiness: score,
      automation_allowed: false, hard_fail: false,
      why: 'inclusion proof missing or not exposed to your role'};
  const business = dims.D11 === 'PASS';
  if (dims.D3 === 'PASS')
    return {verdict: 'VERIFIED_FOR_INTEGRITY', readiness: score,
      automation_allowed: business, hard_fail: false,
      why: business ? 'integrity + inclusion + consistency verified'
        : 'integrity verified; business context still REVIEW_REQUIRED'};
  return {verdict: 'VERIFIED_WITH_LIMITATIONS', readiness: score,
    automation_allowed: false, hard_fail: false,
    why: 'inclusion verified, append-only consistency not exposed/verified'};
};

// Display-only score. Zero on any hard-fail; never overrides the verdict.
window.wbReadiness = (dims) => {
  if (dims.D1 === 'FAIL' || dims.D2 === 'FAIL' || dims.D6 === 'FAIL'
      || dims.D8 === 'FAIL' || dims.D3 === 'FAIL'
      || dims.D9 === 'UNSUPPORTED_CRITICAL_ALGORITHM'
      || dims.D11 === 'DISPUTED') return 0;
  const g = (v) => v === 'PASS' ? 1 : 0;
  const val = 0.25 * g(dims.D1) + 0.18 * g(dims.D2) + 0.15 * g(dims.D3)
    + 0.12 * (dims.D6 === 'FAIL' ? 0 : 1) + 0.10 * g(dims.D7)
    + 0.07 * g(dims.D4) + 0.05 * g(dims.D5) + 0.04 * 0 + 0.04 * g(dims.D9);
  return Math.round(val * 100) / 100;
};

const WB_STATE_MAP = {
  QUARANTINED: 'CAPTURED → HASHED → PROOF_PENDING',
  SCANNED_CLEAN: 'HASHED (scanned) → PROOF_PENDING',
  ADMISSIBLE: 'INCLUSION_PROOF_VERIFIED (if root present)',
  REJECTED: 'REVIEW_REQUIRED → NOT_USABLE_FOR_AUTOMATION'};

window.wbOpen = async (id) => {
  const d = await get('/evidence/' + id);
  const chain = await wbTry('/evidence/' + id + '/chain');
  const derivs = await wbTry('/evidence/' + id + '/derivatives');
  const contracts = wbCanAudit()
    ? await wbTry('/evidence/' + id + '/contracts') : null;
  const proof = wbCanAudit()
    ? await wbTry('/evidence/' + id + '/merkle-proof') : null;
  const immут = await wbTry('/evidence/' + id + '/immutability');
  // Server-verified append-only consistency between the two latest root
  // checkpoints (Finalis Evidence Transparency Log). Needs >= 2 checkpoints;
  // with fewer, append-only stays NOT_EXPOSED (never assumed).
  let consistency = null;
  if (wbCanAudit()) {
    const roots = await wbTry('/evidence/merkle-roots');
    if (roots && roots.length >= 2) {
      const cur = roots[roots.length - 1].batch_id;
      const prev = roots[roots.length - 2].batch_id;
      const d = await wbTry('/evidence/merkle-roots/' + cur
        + '/consistency?previous_root_id=' + prev);
      if (d) consistency = {ok: d.append_only_verified,
                            status: d.status, data: d};
    }
  }
  const dims = wbProofAlgebra(d, proof, derivs, contracts, consistency);
  const verdict = wbVerdict(dims);
  wbRender(d, {chain, derivs, contracts, proof, immut: immут, consistency,
               dims, verdict});
};

window.wbRender = (d, x) => {
  const show = (pid) => { $(pid).hidden = false; };
  ['wb-p-detail', 'wb-p-inclusion', 'wb-p-consistency', 'wb-p-algebra',
   'wb-p-state', 'wb-p-derivative', 'wb-p-contract', 'wb-p-provenance',
   'wb-p-timestamp', 'wb-p-scitt', 'wb-p-crypto', 'wb-p-conflict',
   'wb-p-report', 'wb-p-report-artifact', 'wb-p-graph'].forEach(show);
  window.WB_EVIDENCE_ID = d.id;
  wbLoadReports(d.id);
  const yn = (b) => b ? '<b class="ok">yes</b>' : '<b class="err">no</b>';
  const hashV = d.integrity ? d.integrity.sha256 : null;

  // --- Evidence Detail (escaped) ---
  $('wb-detail-body').innerHTML = `
    <ul>
    <li>evidence id: <code>${esc(d.id)}</code></li>
    <li>case id: <code>${esc(d.case_id || '—')}</code></li>
    <li>type: ${esc(d.evidence_type)} · state:
      <b>${esc(d.state)}</b> · sensitivity: ${esc(d.sensitivity)}</li>
    <li>original filename (metadata only):
      ${esc(d.original_filename || '—')}</li>
    <li>declared mime: ${esc(d.declared_mime || '—')} · detected:
      ${esc(d.detected_mime || '—')} · mismatch: ${yn(d.mime_mismatch)}</li>
    <li>size: ${esc(String(d.size_bytes ?? '—'))} bytes</li>
    <li>content hash (sha-256):
      <code>${esc(hashV || 'not yet computed')}</code></li>
    <li>hash algorithm: ${esc(d.integrity ? d.integrity.algorithm
      : 'unknown')} · integrity valid: ${yn(d.integrity
      && d.integrity.valid)}</li>
    <li>human verified: ${yn(d.human_verified)} · legal hold:
      ${yn(d.legal_hold)} · injection risk: ${esc(String(
        d.injection_risk))}</li>
    <li>scan: ${esc(d.scan.provider)} (${d.scan.is_mock ? 'MOCK' : 'real'})
      · status ${esc(d.scan.status)}</li>
    </ul>`;

  // --- Merkle inclusion ---
  const p = x.proof;
  $('wb-inclusion-body').innerHTML = p == null ?
    `<p><i>Inclusion proof not available to your role
     (requires audit.view), or no Merkle root has been generated yet.</i>
     Status: <b>PROOF_MISSING / SERVER_REVIEW_REQUIRED</b>.</p>` :
    `<ul>
     <li>leaf hash: <code>${esc(p.leaf_hash)}</code></li>
     <li>leaf index: ${esc(String(p.index))} · tree size:
       ${esc(String(p.size))}</li>
     <li>hash algorithm: sha-256 (RFC 9162 style)</li>
     <li>proof path (${(p.path || []).length} nodes):
       ${(p.path || []).map(([h, r]) =>
         `<code>${esc(String(r))}:${esc(h.slice(0, 10))}…</code>`)
         .join(' ') || '<i>root is the leaf</i>'}</li>
     <li>stored root: <code>${esc(p.root)}</code></li>
     <li>inclusion status: <b class="${p.verifies ? 'ok' : 'err'}">
       ${p.verifies ? 'VERIFIED' : 'NOT_VERIFIED / ROOT_MISMATCH'}</b></li>
     </ul>
     <p><small>Merkle proof explains inclusion. It does not explain business
     truth.</small></p>`;

  // --- Merkle consistency / append-only (server-verified) ---
  const c = x.consistency;
  const CMSG = {
    VERIFIED: 'Merkle consistency proof is server-verified.',
    NOT_VERIFIED: 'Append-only consistency is not verified.',
    PROOF_MISSING: 'Historical leaf order was not stored, so consistency '
      + 'proof cannot be reconstructed.',
    ROOT_NOT_FOUND: 'A referenced root checkpoint was not found for this '
      + 'tenant.',
    INVALID_RANGE: 'Invalid range: previous tree size exceeds current tree '
      + 'size.',
    UNSUPPORTED_ALGORITHM: 'Unsupported hash algorithm — verification '
      + 'refused.',
    SERVER_REVIEW_REQUIRED: 'Generated proof failed server-side '
      + 'verification — review required.'};
  $('wb-consistency-body').innerHTML = c == null ?
    `<p><b>Append-only status: NOT_VERIFIED / NOT_EXPOSED.</b> Fewer than two
     root checkpoints exist for this tenant (or proof is not available to
     your role), so append-only tree evolution cannot be proven yet.
     Append-only evidence cannot be assumed unless the server exposes and
     verifies consistency data.</p>` :
    `<ul>
     <li>previous tree size: ${esc(String(c.data.previous_tree_size))} →
       current tree size: ${esc(String(c.data.current_tree_size))}</li>
     <li>consistency proof nodes:
       ${(c.data.consistency_proof_nodes || []).length}</li>
     <li>status: <b class="${c.status === 'VERIFIED' ? 'ok' : 'err'}">
       ${esc(c.status)}</b> · append-only verified: ${yn(c.ok)}</li>
     <li>${esc(CMSG[c.status] || c.data.reason || '')}</li>
     <li><small>checkpoint signatures: NOT_IMPLEMENTED · witness
       cosignatures: NOT_IMPLEMENTED · SCITT receipts: NOT_IMPLEMENTED</small>
       </li>
     </ul>
     <p><small>Merkle consistency proves append-only tree evolution only;
     it does not prove legal validity. Server-side Evidence verification
     remains authoritative.</small></p>`;

  // --- Proof algebra / verdict ---
  const dims = x.dims, v = x.verdict;
  const HARD = {D1: 1, D2: 1, D3: 1, D6: 1, D7: 1, D8: 1, D9: 1, D11: 1};
  const DIM_NAMES = {D1: 'HashIntegrity', D2: 'MerkleInclusion',
    D3: 'MerkleConsistency', D4: 'TimestampEvidence', D5: 'ProvenanceSignal',
    D6: 'DerivativeChain', D7: 'ContractLink', D8: 'TenantIsolation',
    D9: 'AlgorithmAgility', D10: 'Freshness', D11: 'BusinessContext'};
  $('wb-algebra-body').innerHTML = `
    <table><tr><th>Dim</th><th>Dimension</th><th>State</th>
      <th>Hard-fail?</th></tr>` +
    Object.keys(DIM_NAMES).map(k => {
      const st = dims[k];
      const bad = ['FAIL', 'DISPUTED',
        'UNSUPPORTED_CRITICAL_ALGORITHM'].includes(st);
      return `<tr><td>${k}</td><td>${esc(DIM_NAMES[k])}</td>
        <td><b class="${st === 'PASS' ? 'ok' : (bad ? 'err' : '')}">
        ${esc(st)}</b></td>
        <td>${HARD[k] ? (bad ? '<b class="err">HARD-FAIL</b>' : 'hard')
          : 'soft'}</td></tr>`;
    }).join('') + '</table>' + `
    <p><b>EvidenceVerdict:</b>
      <b class="${v.verdict.startsWith('VERIFIED') ? 'ok' : 'err'}">
      ${esc(v.verdict)}</b><br>
      <b>EvidenceProofReadiness (NON-AUTHORITATIVE UI SUMMARY):</b>
      ${esc(String(v.readiness))}
      ${v.readiness === 0 ? '<b class="err">(zero — a hard-fail dimension '
        + 'blocks it; positive signals cannot average it away)</b>' : ''}<br>
      <b>automation_allowed (display only):</b> ${yn(v.automation_allowed)}
      <br><small>Why not stronger: ${esc(v.why)}. A display score cannot
      unlock actions; server decisions remain authoritative. Integrity
      verification and business truth are separate verdicts.</small></p>`;

  // --- Verification state machine ---
  $('wb-state-body').innerHTML = `
    <ul><li>current server state: <b>${esc(d.state)}</b></li>
    <li>conceptual mapping: ${esc(WB_STATE_MAP[d.state]
      || 'REVIEW_REQUIRED')}</li>
    <li>blocking warning: ${v.hard_fail
      ? '<b class="err">' + esc(v.why) + ' — failed proof blocks automation</b>'
      : '<i>none from the proof algebra</i>'}</li>
    <li>allowed next action: ${wbCanAnalyze()
      ? 'verify-integrity (server-authoritative)'
      : '<i>read-only for your role</i>'}</li></ul>
    <p><small>Verification state is server-authoritative. UI state
    explanation cannot unlock actions.</small></p>`;

  // --- Derivative chain ---
  const dv = x.derivs;
  $('wb-derivative-body').innerHTML = dv == null ?
    '<p><i>Derivatives not available to your role.</i></p>' :
    (dv.length ? '<ul>' + dv.map(k => `<li>
      kind: ${esc(k.derivative_kind || k.kind || 'derivative')} ·
      parent: <code>${esc((k.parent_evidence_id || d.id).slice(0, 8))}</code>
      · child hash: <code>${esc((k.manifest_hash || k.child_hash
        || '—')).slice(0, 12)}…</code>
      · confidence: ${esc(String(k.confidence ?? '—'))}
      ${k.is_placeholder ? ' · <b class="err">placeholder (SCAFFOLDED_ONLY)'
        + '</b>' : ''}
      ${(k.confidence >= 0.99 && !(d.integrity && d.integrity.valid))
        ? ' · <b class="err">derivative cannot exceed unverified parent</b>'
        : ''}</li>`).join('') + '</ul>'
     : '<p><i>No derivatives. A derivative is not stronger than its '
       + 'parent evidence.</i></p>') +
    '<p><small>Derivative evidence must preserve parent linkage. OCR '
    + 'derivative generation is SCAFFOLDED_ONLY / not part of V-F.</small></p>';

  // --- Contract history ---
  const ct = x.contracts;
  $('wb-contract-body').innerHTML = ct == null ?
    '<p><i>Contract history requires audit.view.</i></p>' :
    (ct.length ? '<table><tr><th>Contract</th><th>Decision</th>' +
      '<th>Final</th><th>Causal</th><th>Hash</th><th>When</th></tr>' +
      ct.map(r => `<tr><td><small>${esc(r.id.slice(0, 8))}</small></td>
        <td>${esc(r.decision_type)}</td>
        <td><b>${esc(r.final_decision)}</b></td>
        <td>${esc(r.causal_result || '—')}</td>
        <td><code>${esc((r.contract_hash || '—').slice(0, 10))}…</code></td>
        <td><small>${esc(r.created_at)}</small></td></tr>`).join('')
      + '</table>' : '<p><i>No contract events reference this evidence.</i></p>')
    + '<p><small>Contract history is append-oriented and cannot be rewritten '
    + 'from the UI.</small></p>';

  // --- Provenance / C2PA (MISSING) ---
  $('wb-provenance-body').innerHTML =
    `<p><b>MISSING</b> — no provenance/C2PA API is exposed by the server;
     no C2PA data is faked. Provenance is a signal, not final truth; C2PA
     provenance is not final truth and does not prove legal validity.</p>`;

  // --- Timestamp / evidence record (MISSING) ---
  const im = x.immut;
  $('wb-timestamp-body').innerHTML =
    `<p><b>MISSING</b> — no RFC 3161 timestamp token and no RFC 4998
     evidence record are exposed. Timestamping proves existence at a time;
     it does not prove business truth.</p>` +
    (im ? `<p><small>Local immutability (not external anchoring): native
     WORM ${yn(im.native_worm)}; ${esc(im.note || '')}</small></p>` : '');

  // --- SCITT (MISSING) ---
  $('wb-scitt-body').innerHTML =
    `<p><b>MISSING</b> — SCITT statement/receipt integration is not
     implemented; no external transparency service is called. A receipt is
     not the same as business truth.</p>`;

  // --- Crypto agility / PQC ---
  const alg = d.integrity ? d.integrity.algorithm : null;
  const fam = !alg ? 'UNKNOWN'
    : (/(md5|sha1|sha-1)/i.test(alg) ? 'DEPRECATED / UNSUPPORTED'
      : 'CLASSICAL_ONLY');
  $('wb-crypto-body').innerHTML = `<ul>
    <li>hash algorithm: ${esc(alg || 'unknown')}</li>
    <li>signature algorithm: <i>not exposed</i></li>
    <li>algorithm family: <b>${esc(fam)}</b></li>
    <li>PQC readiness: <b>UNKNOWN / NOT_EXPOSED</b> (server does not enforce
      a PQC policy)</li></ul>
    <p><small>${/(md5|sha1|sha-1)/i.test(alg || '')
      ? 'Unknown or deprecated algorithms require review.'
      : 'Informational only. Unknown or deprecated algorithms require '
      + 'review.'}</small></p>`;

  // --- Conflict matrix ---
  const conflicts = [];
  if (dims.D1 === 'FAIL') conflicts.push(
    ['Integrity', 'hash mismatch', 'BLOCKS AUTOMATION']);
  if (dims.D2 === 'FAIL') conflicts.push(
    ['Integrity', 'Merkle root mismatch', 'REQUIRES REVIEW']);
  if (dims.D2 === 'NOT_EXPOSED') conflicts.push(
    ['Integrity', 'inclusion proof missing/not exposed', 'REVIEW']);
  if (dims.D3 !== 'PASS') conflicts.push(
    ['Chain', 'append-only consistency not verified', 'REVIEW']);
  if (dims.D6 === 'FAIL') conflicts.push(
    ['Chain', 'derivative parent missing or over-trust', 'BLOCKS TRUST']);
  conflicts.push(['Provenance', 'provenance API MISSING', 'signal only']);
  conflicts.push(['Timestamp', 'timestamp evidence MISSING', 'no proof of time']);
  conflicts.push(['SCITT', 'receipt MISSING', 'not business truth']);
  if (dims.D9 === 'UNSUPPORTED_CRITICAL_ALGORITHM') conflicts.push(
    ['CryptoAgility', 'deprecated/unsupported algorithm', 'REVIEW']);
  if (dims.D11 !== 'PASS') conflicts.push(
    ['Business', 'evidence integrity vs disputed/unverified outcome',
     'integrity ≠ business truth']);
  $('wb-conflict-body').innerHTML =
    '<table><tr><th>Category</th><th>Conflict</th><th>Effect</th></tr>' +
    conflicts.map(([a, b, cc]) => `<tr><td>${esc(a)}</td><td>${esc(b)}</td>
      <td><b>${esc(cc)}</b></td></tr>`).join('') + '</table>';

  // --- Human report ---
  $('wb-report-body').innerHTML = `<ul>
    <li>What was checked: hash integrity, Merkle inclusion, append-only
      consistency (if exposed), derivative linkage, contract linkage,
      tenant isolation, algorithm family.</li>
    <li>Hash checked: <code>${esc(hashV || 'not computed')}</code></li>
    <li>Proof root used: <code>${esc(x.proof ? x.proof.root
      : 'none / not exposed')}</code></li>
    <li>Passed: ${esc(Object.keys(dims).filter(k => dims[k] === 'PASS')
      .join(', ') || 'none')}</li>
    <li>Failed: ${esc(Object.keys(dims).filter(k =>
      ['FAIL', 'DISPUTED', 'UNSUPPORTED_CRITICAL_ALGORITHM']
      .includes(dims[k])).join(', ') || 'none')}</li>
    <li>Unknown/missing: ${esc(Object.keys(dims).filter(k =>
      ['UNKNOWN', 'NOT_EXPOSED'].includes(dims[k])).join(', ')
      || 'none')}</li>
    <li>Verdict: <b>${esc(v.verdict)}</b> · readiness
      ${esc(String(v.readiness))} (NON-AUTHORITATIVE UI SUMMARY)</li>
    <li>Signed verification report export: <b>MISSING</b>.</li>
    </ul><p><small>UI explanations are not legal advice. Evidence
    verification does not automatically approve a case outcome.</small></p>`;

  // --- Chain graph (indented relationship view) ---
  $('wb-graph-body').innerHTML = `<ul>
    <li>case <code>${esc((d.case_id || '—').slice(0, 8))}</code>
      <ul><li>evidence <code>${esc(d.id.slice(0, 8))}</code> ·
        ${esc(d.evidence_type)}
        <ul>
        <li>derivatives: ${x.derivs == null ? 'n/a'
          : x.derivs.length}</li>
        <li>contract events: ${x.contracts == null ? 'n/a'
          : x.contracts.length}</li>
        <li>proof root: ${x.proof ? 'present' : 'none/not exposed'}</li>
        <li>timestamp/provenance/SCITT: MISSING slots</li>
        <li>algorithm: ${esc(alg || 'unknown')}</li>
        <li>warning: ${v.hard_fail ? esc(v.why) : 'none'}</li>
        </ul></li></ul></li></ul>`;

  $('workbench-section').scrollIntoView();
  wbMsg('Opened proof workbench for ' + d.id.slice(0, 8)
    + ' — server-side verification remains authoritative.', true);
};

// --- Proof Report Package (EVIDENCE-REPORT-C2) ---------------------------
window.wbRenderReport = (m, pkg) => {
  const yn = (b) => b ? '<b class="ok">yes</b>' : '<b class="err">no</b>';
  $('wb-report-artifact-body').innerHTML = `<ul>
    <li>report_id: <code>${esc(m.report_id)}</code></li>
    <li>report_hash: <code>${esc((m.report_hash || '').slice(0, 20))}…</code>
      <small>(Report hash is implemented.)</small></li>
    <li>package_hash: <code>${esc(((pkg && pkg.package_hash)
      || '').slice(0, 20))}…</code></li>
    <li>canonicalization_version: ${esc(m.canonicalization_version)}
      (${esc(m.canonicalization_profile)})</li>
    <li>report_hash_input_schema_version:
      ${esc(m.report_hash_input_schema_version)}</li>
    <li>report_signature_status: <b>${esc(m.report_signature_status)}</b>
      · signature_envelope_type: ${esc(m.signature_envelope_type)}
      <small>(Report signing requires configured signing infrastructure.)
      </small></li>
    <li>redaction_profile: ${esc(m.redaction_profile)} · safe view
      available: ${yn(m.safe_view_available)}
      <small>(Safe view is not a separate proof.)</small></li>
    <li>replay_status: ${esc(m.replay_status)} · generated_at:
      <small>${esc(m.generated_at)}</small></li>
    <li>final_technical_verdict: <b class="${
      (m.final_verdict || '').startsWith('VERIFIED') ? 'ok' : 'err'}">
      ${esc(m.final_verdict)}</b> · warnings ${esc(String(
        m.warnings_count))} · conflicts ${esc(String(m.conflicts_count))}
      · missing capabilities ${esc(String(m.missing_capabilities_count))}</li>
    </ul>
    <p><small>UI report display is not legal advice. Cryptographic
    verification is not the same as legal validity. Server-side Evidence
    logic remains authoritative.</small></p>`;
};

window.wbLoadReports = async (id) => {
  const rows = await wbTry('/evidence/' + id + '/proof-reports');
  const canGen = wbCanAudit();
  const head = canGen
    ? `<p><button onclick="wbGenReport('${esc(id)}')">Generate proof
       report</button> <small>(canonical, replayable, server-verified)
       </small></p>` : '<p><small>Proof reports require audit.view.</small></p>';
  if (rows && rows.length) {
    const latest = rows[rows.length - 1];
    const full = await wbTry('/evidence/proof-reports/' + latest.report_id);
    if (full) wbRenderReport(full.report_metadata, full.package);
    $('wb-report-artifact-body').innerHTML = head
      + $('wb-report-artifact-body').innerHTML
      + `<p><small>${rows.length} report artifact(s) on record — new
         reports never overwrite prior ones.</small></p>`;
  } else {
    $('wb-report-artifact-body').innerHTML = head
      + '<p><i>No proof report generated yet.</i></p>';
  }
};

window.wbGenReport = async (id) => {
  const {ok, data} = await send('POST',
    '/evidence/' + id + '/proof-reports', {});
  if (!ok) { wbMsg('Refused: ' + (data.detail || ''), false); return; }
  wbRenderReport(data.report_metadata, data.package);
  wbMsg('Proof report generated — report_hash '
    + (data.report_metadata.report_hash || '').slice(0, 12)
    + '. Report signing requires configured signing infrastructure.', true);
};

// Case-first entry from the case detail row.
window.proofFor = async (caseId) => {
  await wbLoadList(caseId);
  $('workbench-section').scrollIntoView();
};
"""

# ===========================================================================
# CORE-A1 — Finalis AI Employee identity + authority boundary (portal view).
# ===========================================================================
AIEMP_SECTIONS = """
<section id="aiemp-section"><h2>Finalis AI Employee</h2>
<p><small><b>Finalis AI Employee is not a human user.</b> It is a
tenant-scoped, non-autonomous worker that can propose work and draft outputs
within an authority boundary. <b>AI Employee cannot override server-side
policy.</b> <b>AI Employee cannot verify memory as human truth.</b>
<b>AI Employee cannot override consent.</b> <b>AI Employee cannot rewrite
evidence.</b> <b>AI Employee cannot approve its own work.</b> Human approval
is required for sensitive actions. <b>Production autonomy is disabled.</b>
Server-side policy remains authoritative. This is not a production autonomous
worker.</small></p>
<div id="aiemp-profile"><i>Loading AI Employee…</i></div>
</section>
"""

AIEMP_JS = """
window.loadAIEmployeeSection = async (me) => {
  let emps; try { emps = await get('/ai-employees'); }
  catch (e) { $('aiemp-profile').innerHTML =
    '<i>AI Employee profile is not available for your role.</i>'; return; }
  if (!emps || !emps.length) {
    $('aiemp-profile').innerHTML = '<i>No AI Employee registered.</i>';
    return; }
  const e = emps[0];
  const chips = (arr) => (arr || []).map(a =>
    `<span class="badge">${esc(a)}</span>`).join(' ');
  $('aiemp-profile').innerHTML = `
    <p><b>${esc(e.display_name)}</b> · identity type
      <b>${esc(e.identity_type)}</b> · status ${esc(e.status)} · role
      ${esc(e.role)} · production autonomy:
      <b class="err">${e.production_autonomy_enabled ? 'ENABLED'
        : 'disabled'}</b></p>
    <p><b>Segment capabilities:</b> ${chips(e.segment_capabilities)}</p>
    <p><b>Read-only actions:</b> ${chips(e.read_only_action_types)}</p>
    <p><b>Draft-only actions:</b> ${chips(e.draft_only_action_types)}</p>
    <p><b>Approval-required actions:</b>
      ${chips(e.approval_required_action_types)}</p>
    <p><b class="err">Forbidden actions:</b>
      ${chips(e.forbidden_action_types)}</p>
    <ul>${(e.honesty_labels || []).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>`;
};
"""

# ===========================================================================
# CORE-A2 — Secure Work Intake Registry / Task Delegation Inbox (portal view).
# ===========================================================================
TASKS_SECTIONS = """
<section id="tasks-section"><h2>Task Delegation Inbox</h2>
<p><small><b>Task creation does not execute side effects.</b> <b>AI Employee
can draft or prepare work only within its authority boundary.</b>
<b>Sensitive actions require human approval.</b> <b>Task text is treated as
untrusted input.</b> <b>Task contract defines the accepted purpose, scope and
boundaries.</b> <b>Input security flags are advisory; server-side authority
decision remains authoritative.</b> Server-side policy remains authoritative.
<b>Slack and Microsoft Teams intake are not implemented in this mission.</b>
<b>Run Ledger is not implemented in this mission.</b> <b>Tool Broker is not
implemented in this mission.</b></small></p>
<div id="tasks-create" hidden>
  <select id="task-type"></select>
  <input id="task-title" placeholder="task title" style="max-width:12rem"/>
  <input id="task-desc" placeholder="description (untrusted)"
    style="max-width:16rem"/>
  <input id="task-subject" placeholder="subject id (case/customer)"
    style="max-width:10rem"/>
  <button id="task-create-btn" onclick="createTask()">Delegate task</button>
</div>
<div id="task-msg"></div>
<div id="tasks-list"><i>Loading tasks…</i></div>
<div id="task-detail"></div>
</section>
"""

TASKS_JS = """
window.loadTasksSection = async (me) => {
  $('tasks-create').hidden = !(me.permissions.includes('case.update'));
  try {
    const t = await get('/ai-tasks/types');
    $('task-type').innerHTML = Object.keys(t.task_types).map(k =>
      `<option value="${esc(k)}">${esc(k)}</option>`).join('');
  } catch (e) {}
  await loadTasks();
};

window.loadTasks = async () => {
  let rows; try { rows = await get('/ai-tasks'); }
  catch (e) { $('tasks-list').innerHTML =
    '<i>Tasks are not available for your role.</i>'; return; }
  $('tasks-list').innerHTML = rows.length ?
    '<table><tr><th>Type</th><th>Segment</th><th>Status</th>' +
    '<th>Decision</th><th>Risk</th><th></th></tr>' + rows.map(t =>
      `<tr><td>${esc(t.task_type)}</td><td>${esc(t.segment)}</td>
       <td><b>${esc(t.task_status)}</b></td>
       <td>${esc(t.authority_decision)}</td>
       <td>${esc(t.risk_level)}</td>
       <td><button onclick="openTask('${esc(t.task_id)}')">Open</button>
       </td></tr>`).join('') + '</table>' : '<i>No tasks yet.</i>';
};

window.createTask = async () => {
  const body = {task_type: $('task-type').value,
                task_title: $('task-title').value,
                task_description: $('task-desc').value};
  if ($('task-subject').value) {
    body.subject_type = 'case'; body.subject_id = $('task-subject').value; }
  const {ok, data} = await send('POST', '/ai-tasks', body);
  $('task-msg').innerHTML = ok
    ? `<span class="ok">Task ${esc((data.task_status || ''))} — envelope `
      + `${esc((data.canonical_task_envelope_hash || '').slice(0, 10))}…, `
      + `contract ${esc((data.canonical_task_contract_hash || '')
        .slice(0, 10))}…</span>`
    : `<span class="err">Refused: ${esc(data.detail || '')}</span>`;
  if (ok) { await loadTasks(); openTask(data.task_id); }
};

window.openTask = async (id) => {
  const t = await get('/ai-tasks/' + id);
  const chips = (a) => (a || []).map(x =>
    `<span class="badge">${esc(x)}</span>`).join(' ');
  $('task-detail').innerHTML = `
    <h3>${esc(t.task_type)} <span class="badge">${esc(t.task_status)}</span>
      </h3>
    <p>segment ${esc(t.segment)} · purpose ${esc(t.purpose_category)} ·
      priority ${esc(t.priority)} · risk <b>${esc(t.risk_level)}</b>
      <small>(${esc(t.risk_reason)})</small></p>
    <p><b>Authority decision:</b> <b class="${t.authority_hard_fail
      ? 'err' : 'ok'}">${esc(t.authority_decision)}</b>
      <small>${esc(t.authority_reason)}</small></p>
    <p><b>Requires:</b> human approval ${t.requires_human_approval} ·
      consent check ${t.requires_consent_check} · evidence check
      ${t.requires_evidence_check} · tool broker ${t.requires_tool_broker}</p>
    <p><b>Allowed data scopes:</b> ${chips(t.allowed_data_scopes)}</p>
    <p><b class="err">Forbidden data scopes:</b>
      ${chips(t.forbidden_data_scopes)}</p>
    <p><b class="err">Input security flags:</b>
      ${chips(t.input_security_flags)}</p>
    <p><b class="err">Unsafe requested actions:</b>
      ${chips(t.unsafe_requested_actions)}</p>
    <p><b>Envelope hash:</b>
      <code>${esc(t.canonical_task_envelope_hash)}</code></p>
    <p><b>Contract hash:</b>
      <code>${esc(t.canonical_task_contract_hash)}</code></p>
    <p><small>Task description is UNTRUSTED user input:
      <i>${esc(t.task_description)}</i></small></p>
    <ul>${(t.honesty_labels || []).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>`;
};
"""

# ===========================================================================
# CORE-A3 — Run Ledger / Trace Replay Journal (portal view).
# ===========================================================================
RUNS_SECTIONS = """
<section id="runs-section"><h2>Run Ledger</h2>
<p><small><b>Run Ledger records what happened; it does not grant permission
to act.</b> <b>Replay verifies ledger consistency; it does not re-run the
task.</b> <b>Run event Merkle root is an internal checkpoint; it is not
external notarization.</b> <b>No LLM execution is implemented in this
mission.</b> <b>No Tool Broker execution is implemented in this mission.</b>
<b>Human Approval Gate is not implemented in this mission.</b> <b>Trace-ready
fields are internal; external telemetry export is not implemented.</b>
<b>Safe run view is not a separate ledger.</b> <b>Retention fields are
advisory in this build; production retention enforcement is not
implemented.</b> Server-side policy remains authoritative.</small></p>
<div id="runs-list"><i>Loading runs…</i></div>
<div id="run-detail"></div>
</section>
"""

RUNS_JS = """
window.loadRunsSection = async (me) => { await loadRuns(); };

window.loadRuns = async () => {
  let rows; try { rows = await get('/ai-runs'); }
  catch (e) { $('runs-list').innerHTML =
    '<i>Runs are not available for your role.</i>'; return; }
  $('runs-list').innerHTML = rows.length ?
    '<table><tr><th>Run</th><th>Task</th><th>Status</th><th>Events</th>' +
    '<th>Consistency</th><th></th></tr>' + rows.map(r =>
      `<tr><td><small>${esc(r.run_id.slice(0, 8))}</small></td>
       <td><small>${esc((r.task_id || '').slice(0, 8))}</small></td>
       <td><b>${esc(r.run_status)}</b></td><td>${esc(String(
         r.event_count))}</td>
       <td>${esc(r.run_status_consistency)}</td>
       <td><button onclick="openRun('${esc(r.run_id)}')">Open</button>
       </td></tr>`).join('') + '</table>' : '<i>No runs yet.</i>';
};

window.openRun = async (id) => {
  const r = await get('/ai-runs/' + id);
  const evs = r.events || [];
  $('run-detail').innerHTML = `
    <h3>Run ${esc(r.run_id.slice(0, 8))}
      <span class="badge">${esc(r.run_status)}</span></h3>
    <p>task ${esc((r.task_id || '').slice(0, 8))} · employee
      ${esc((r.assigned_ai_employee_id || '').slice(0, 8))} · segment
      ${esc(r.segment)} · risk ${esc(r.risk_level)} · trace
      <code>${esc((r.trace_id || '').slice(0, 8))}</code></p>
    <p><b>Authority:</b> ${esc(r.authority_decision)} ·
      replayed status ${esc(r.replayed_run_status)} · consistency
      <b>${esc(r.run_status_consistency)}</b></p>
    <p><b>event_count</b> ${esc(String(r.event_count))} ·
      <b>latest_event_hash</b> <code>${esc((r.latest_event_hash
        || '').slice(0, 14))}…</code></p>
    <p><b>run_chain_hash</b> <code>${esc((r.run_chain_hash
      || '').slice(0, 14))}…</code> · <b>run_state_hash</b>
      <code>${esc((r.run_state_hash || '').slice(0, 14))}…</code></p>
    <p><b>run_event_merkle_root</b>
      <code>${esc((r.run_event_merkle_root || '').slice(0, 14))}…</code></p>
    <p><button onclick="verifyRun('${esc(id)}')">Verify ledger</button>
      <button onclick="replayRun('${esc(id)}')">Replay</button>
      <span id="run-verify-msg"></span></p>
    <h4>Events (${evs.length})</h4>
    <table><tr><th>#</th><th>Type</th><th>Status</th><th>Hash</th></tr>
      ${evs.map(e => `<tr><td>${esc(String(e.event_index))}</td>
        <td>${esc(e.event_type)}</td><td>${esc(e.event_status)}</td>
        <td><code>${esc((e.event_hash || '').slice(0, 12))}…</code></td>
        </tr>`).join('')}</table>
    <ul>${(r.honesty_labels || []).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>`;
};

window.verifyRun = async (id) => {
  const {ok, data} = await send('POST', '/ai-runs/' + id + '/verify', {});
  $('run-verify-msg').innerHTML = ok
    ? `<b class="${data.verification_status === 'MATCHED' ? 'ok' : 'err'}">
       ${esc(data.verification_status)}</b> (tamper:
       ${data.tamper_detected}) <small>${esc(data.reason)}</small>`
    : `<span class="err">${esc(data.detail || '')}</span>`;
};

window.replayRun = async (id) => {
  const {ok, data} = await send('POST', '/ai-runs/' + id + '/replay', {});
  $('run-verify-msg').innerHTML = ok
    ? `replay <b class="${data.replay_status === 'MATCHED' ? 'ok' : 'err'}">
       ${esc(data.replay_status)}</b> → ${esc(data.replayed_run_status)}
       <small>(current_task_state_comparison:
       ${esc(data.current_task_state_comparison)})</small>`
    : `<span class="err">${esc(data.detail || '')}</span>`;
};
"""

APPROVALS_SECTIONS = """
<section id="approvals-section"><h2>Human Approval Gate</h2>
<ul class="labels"><small>
<li>Approval does not execute the action.</li>
<li>Consume-check validates approval scope only; it does not execute the action.</li>
<li>Approval does not override consent, evidence, RBAC or proof failures.</li>
<li>AI Employee cannot approve its own work.</li>
<li>Only an authorized human approver can approve.</li>
<li>Approval is scoped to this run, task, action and hash state.</li>
<li>Approval grant must be revalidated before future use.</li>
<li>This is not OAuth, GNAP, or an external bearer token.</li>
<li>Server-side policy remains authoritative.</li>
</small></ul>
<div id="approvals-list"><i>Loading approval requests…</i></div>
<div id="approval-detail"></div>
</section>
"""

APPROVALS_JS = """
window.loadApprovalsSection = async (me) => { await loadApprovals(); };

window.loadApprovals = async () => {
  let rows; try { rows = await get('/ai-approvals'); }
  catch (e) { $('approvals-list').innerHTML =
    '<i>Approval requests are not available for your role.</i>'; return; }
  $('approvals-list').innerHTML = rows.length ?
    '<table><tr><th>Request</th><th>Action</th><th>Risk</th><th>Status</th>' +
    '<th>Approver</th><th>Challenge</th><th></th></tr>' + rows.map(a =>
      `<tr><td><small>${esc(a.approval_request_id.slice(0, 8))}</small></td>
       <td>${esc(a.approval_action_type)}</td>
       <td>${esc(a.approval_risk_level)}</td>
       <td><b>${esc(a.approval_status)}</b></td>
       <td>${esc(a.required_approver_role)}</td>
       <td>${a.approval_challenge_required ? 'required' : 'no'}</td>
       <td><button onclick="openApproval('${esc(a.approval_request_id)}')">
         Open</button></td></tr>`).join('') + '</table>'
    : '<i>No approval requests yet.</i>';
};

window.openApproval = async (id) => {
  const a = await get('/ai-approvals/' + id);
  const pkg = a.approval_package || {};
  const acks = pkg.required_acknowledgements || [];
  let grant = null;
  try { grant = await get('/ai-approvals/' + id + '/grant'); } catch (e) {}
  const decided = a.approval_status !== 'PENDING'
    && a.approval_status !== 'CHALLENGE_REQUIRED';
  const ackBoxes = acks.map(r =>
    `<label><input type="checkbox" class="ack" data-ack="${esc(r)}"> ${esc(r)}
     </label>`).join('<br>');
  $('approval-detail').innerHTML = `
    <h3>Approval ${esc(a.approval_request_id.slice(0, 8))}
      <span class="badge">${esc(a.approval_status)}</span></h3>
    <p><b>action</b> ${esc(a.approval_action_type)} · <b>risk</b>
      ${esc(a.approval_risk_level)} · run
      <code>${esc((a.run_id || '').slice(0, 8))}</code> · task
      <code>${esc((a.task_id || '').slice(0, 8))}</code></p>
    <p><b>required approver</b> ${esc(a.required_approver_role)} ×
      ${esc(String(a.required_approver_count))} · dual control
      ${a.dual_control_required ? 'yes' : 'no'} · challenge
      ${a.approval_challenge_required ? '<b>required</b>' : 'no'}</p>
    <p><b>viewed package hash</b>
      <code id="approval-viewed-hash">${esc(a.approval_package_hash)}</code></p>
    <p><b>policy_decision_hash</b> <code>${esc((a.policy_decision_hash
      || '').slice(0, 14))}…</code> · <b>challenge_hash</b>
      <code>${esc((a.approval_challenge_hash || '').slice(0, 14))}…</code></p>
    <p><button onclick="verifyApproval('${esc(id)}')">Verify hashes</button>
      <span id="approval-verify-msg"></span></p>
    <h4>An approval can never unlock</h4>
    <ul>${(pkg.forbidden_unlocks || []).map(f =>
      `<li><small>${esc(f)}</small></li>`).join('')}</ul>
    <h4>Required acknowledgements</h4>
    <div id="approval-acks">${decided ? '<i>decision recorded</i>'
      : ackBoxes}</div>
    ${a.approval_challenge_required && !decided
      ? '<p><label><input type="checkbox" id="approval-challenge"> ' +
        'Challenge completed — I reviewed the exact action, run, task, risk ' +
        'and hash state</label></p>' : ''}
    <p>${decided ? '' :
      `<button onclick="decideApproval('${esc(id)}','approve')">Approve</button>
       <button onclick="decideApproval('${esc(id)}','reject')">Reject</button>
       <button onclick="decideApproval('${esc(id)}','changes')">Request
         changes</button>`}
      ${a.approval_status && a.approval_status.indexOf('APPROVED') === 0
        ? `<button onclick="decideApproval('${esc(id)}','revoke')">Revoke
           </button>` : ''}
      <span id="approval-decide-msg"></span></p>
    ${grant ? `<h4>Approval grant</h4>
      <p><b>${esc(grant.grant_status)}</b> · type
        <code>${esc(grant.grant_type)}</code> · usage
        ${esc(grant.grant_usage_policy)}</p>
      <p><b>grant_hash</b> <code>${esc((grant.approval_grant_hash
        || '').slice(0, 14))}…</code> · <b>nonce_hash</b>
        <code>${esc((grant.grant_nonce_hash || '').slice(0, 14))}…</code></p>
      <p><button onclick="consumeCheck('${esc(id)}')">Consume-check</button>
        <span id="approval-consume-msg"></span></p>
      <p><small>Approval grant must be revalidated before future use.
        Consume-check validates approval scope only; it does not execute the
        action. This is not OAuth, GNAP, or an external bearer token.</small>
        </p>` : ''}
    <p><small>Approval does not execute the action. Only an authorized human
      approver can approve. AI Employee cannot approve its own work.</small></p>
    <ul>${(a.honesty_labels || []).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>`;
};

window.decideApproval = async (id, kind) => {
  const path = {approve: 'approve', reject: 'reject', changes: 'changes',
                revoke: 'revoke'}[kind];
  const body = {decision_reason: 'via portal'};
  if (kind === 'approve') {
    body.viewed_package_hash = $('approval-viewed-hash').textContent;
    const acks = {};
    document.querySelectorAll('#approval-acks .ack').forEach(cb => {
      acks[cb.dataset.ack] = cb.checked; });
    body.acknowledgements = acks;
    const ch = $('approval-challenge');
    body.challenge_passed = ch ? ch.checked : false;
  }
  const {ok, data} = await send('POST', '/ai-approvals/' + id + '/' + path,
                                body);
  $('approval-decide-msg').innerHTML = ok
    ? `<b class="ok">${esc(data.approval_status)}</b>`
    : `<span class="err">${esc(data.detail || 'denied')}</span>`;
  if (ok) { openApproval(id); loadApprovals(); }
};

window.consumeCheck = async (id) => {
  const {ok, data} = await send('POST',
    '/ai-approvals/' + id + '/consume-check', {});
  $('approval-consume-msg').innerHTML = ok
    ? `<b class="${data.grant_validation_status === 'VALID' ? 'ok' : 'err'}">
       ${esc(data.grant_validation_status)}</b> <small>(can_execute_now:
       ${data.can_execute_now}, drift: ${data.drift_detected}) ${esc(
       data.reason)}</small>`
    : `<span class="err">${esc(data.detail || '')}</span>`;
};

window.verifyApproval = async (id) => {
  const {ok, data} = await send('POST', '/ai-approvals/' + id + '/verify', {});
  $('approval-verify-msg').innerHTML = ok
    ? `<b class="${data.verification_status === 'MATCHED' ? 'ok' : 'err'}">
       ${esc(data.verification_status)}</b> <small>(challenge:
       ${esc(data.challenge_bound_to_package)}) ${esc(data.reason)}</small>`
    : `<span class="err">${esc(data.detail || '')}</span>`;
};
"""

LIFECYCLE_SECTIONS = """
<section id="lifecycle-section"><h2>Task Lifecycle Kernel</h2>
<ul class="labels"><small>
<li>State transition does not execute the action.</li>
<li>Transition dry-run does not mutate state.</li>
<li>Transition replay reconstructs lifecycle state; it does not re-run the task.</li>
<li>Transition reconciliation compares stored and replayed state; it does not auto-heal silently.</li>
<li>Completion Loop checks readiness only; it does not execute the task.</li>
<li>Approval grant validation does not call external providers.</li>
<li>Tool Broker is not implemented in this mission.</li>
<li>LLM runtime is not implemented in this mission.</li>
<li>Server-side task state is authoritative.</li>
</small></ul>
<p id="lifecycle-graph"><i>Loading state machine…</i></p>
<div id="lifecycle-list"><i>Loading tasks…</i></div>
<div id="lifecycle-detail"></div>
</section>
"""

LIFECYCLE_JS = """
window.loadLifecycleSection = async (me) => {
  try {
    const g = await get('/ai-tasks/state-machine/verify');
    $('lifecycle-graph').innerHTML =
      `Transition graph: <b class="${g.graph_verification_status === 'MATCHED'
        ? 'ok' : 'err'}">${esc(g.graph_verification_status)}</b>
       <small>(${esc(String(g.states_checked))} states, ${esc(String(
         g.edges_checked))} edges)</small>`;
  } catch (e) { $('lifecycle-graph').innerHTML = ''; }
  await loadLifecycleTasks();
};

window.loadLifecycleTasks = async () => {
  let tasks; try { tasks = await get('/ai-tasks'); }
  catch (e) { $('lifecycle-list').innerHTML =
    '<i>Tasks are not available for your role.</i>'; return; }
  const rows = await Promise.all(tasks.slice(0, 25).map(async t => {
    let s; try { s = await get('/ai-tasks/' + t.task_id + '/state'); }
    catch (e) { return ''; }
    return `<tr><td><small>${esc(t.task_id.slice(0, 8))}</small></td>
      <td>${esc(t.task_type)}</td><td><b>${esc(s.lifecycle_state)}</b></td>
      <td>${esc(s.completion_status)}</td>
      <td>${esc(s.reconciliation_status)}</td>
      <td><button onclick="openLifecycle('${esc(t.task_id)}')">Open</button>
      </td></tr>`; }));
  $('lifecycle-list').innerHTML = tasks.length
    ? '<table><tr><th>Task</th><th>Type</th><th>State</th><th>Completion</th>' +
      '<th>Reconcile</th><th></th></tr>' + rows.join('') + '</table>'
    : '<i>No tasks yet.</i>';
};

window.openLifecycle = async (id) => {
  const s = await get('/ai-tasks/' + id + '/state');
  const tr = await get('/ai-tasks/' + id + '/transitions');
  const comp = await get('/ai-tasks/' + id + '/completion');
  $('lifecycle-detail').innerHTML = `
    <h3>Task ${esc(id.slice(0, 8))}
      <span class="badge">${esc(s.lifecycle_state)}</span></h3>
    <p><b>task_state_hash</b> <code>${esc((s.task_state_hash
      || '').slice(0, 14))}…</code> · version ${esc(String(s.task_version))}
      · risk ${esc(s.risk_level)}</p>
    <p><b>Allowed next:</b> ${(s.allowed_next_transitions || []).map(e =>
      `<button onclick="applyTransition('${esc(id)}','${esc(e.event)}')">
       ${esc(e.event)}</button>`).join(' ') || '<i>none</i>'}
      <span id="lifecycle-msg"></span></p>
    <p><button onclick="verifyLifecycle('${esc(id)}')">Verify</button>
      <button onclick="replayLifecycle('${esc(id)}')">Replay</button>
      <button onclick="reconcileLifecycle('${esc(id)}')">Reconcile</button>
      <span id="lifecycle-vmsg"></span></p>
    <h4>Completion — ${esc(comp.completion_status)}</h4>
    <ul>${(comp.completion_blockers || []).map(b =>
      `<li><small>${esc(b.blocker_code)} [${esc(b.severity)}] —
       ${esc(b.remediation_hint)}</small></li>`).join('') ||
      '<li><small>no blockers</small></li>'}</ul>
    <h4>Transition history (${tr.transitions.length})</h4>
    <table><tr><th>#</th><th>From</th><th>Event</th><th>To</th><th>Status</th>
      </tr>${tr.transitions.map((t, i) => `<tr><td>${i}</td>
      <td>${esc(t.from_state)}</td><td>${esc(t.transition_event)}</td>
      <td>${esc(t.to_state)}</td><td>${esc(t.transition_status)}</td></tr>`)
      .join('')}</table>
    <ul>${(s.honesty_labels || []).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>`;
};

window.applyTransition = async (id, event) => {
  const {ok, data} = await send('POST', '/ai-tasks/' + id + '/transitions',
                                {transition_event: event});
  $('lifecycle-msg').innerHTML = ok
    ? `<b class="${data.transition_status === 'ALLOWED' ? 'ok' : 'err'}">
       ${esc(data.transition_status)}</b> ${esc(data.blocked_reason || '')}`
    : `<span class="err">${esc(data.detail || '')}</span>`;
  if (ok && data.applied) { openLifecycle(id); loadLifecycleTasks(); }
};

window.verifyLifecycle = async (id) => {
  const {data} = await send('POST', '/ai-tasks/' + id + '/transitions/verify',
                            {});
  $('lifecycle-vmsg').innerHTML =
    `verify <b class="${data.verification_status === 'MATCHED' ? 'ok'
      : 'err'}">${esc(data.verification_status)}</b>`;
};
window.replayLifecycle = async (id) => {
  const {data} = await send('POST', '/ai-tasks/' + id + '/transitions/replay',
                            {});
  $('lifecycle-vmsg').innerHTML = `replay <b>${esc(data.replay_status)}</b> → `
    + esc(data.replayed_state);
};
window.reconcileLifecycle = async (id) => {
  const {data} = await send('POST',
    '/ai-tasks/' + id + '/transitions/reconcile', {});
  $('lifecycle-vmsg').innerHTML =
    `reconcile <b class="${data.reconciliation_status === 'MATCHED' ? 'ok'
      : 'err'}">${esc(data.reconciliation_status)}</b>
     (auto_healed: ${data.auto_healed})`;
};
"""

ARTIFACTS_SECTIONS = """
<section id="artifacts-section"><h2>Artifact System</h2>
<ul class="labels"><small>
<li>Artifact creation does not execute the action.</li>
<li>Artifact creation does not send customer messages.</li>
<li>Artifact creation does not call external providers.</li>
<li>AI draft content is not human-verified truth.</li>
<li>Claim graph records local support status; it does not create legal truth.</li>
<li>Artifact quarantine preserves the artifact but blocks readiness and future use.</li>
<li>Server-side artifact truth is authoritative.</li>
<li>Document export is not implemented in this mission.</li>
<li>C2PA/Sigstore/DSSE/SLSA/in-toto are not implemented in this mission.</li>
</small></ul>
<div id="artifacts-list"><i>Loading artifacts…</i></div>
<div id="artifact-detail"></div>
</section>
"""

ARTIFACTS_JS = """
window.loadArtifactsSection = async (me) => { await loadArtifacts(); };

window.loadArtifacts = async () => {
  let rows; try { rows = await get('/ai-artifacts'); }
  catch (e) { $('artifacts-list').innerHTML =
    '<i>Artifacts are not available for your role.</i>'; return; }
  $('artifacts-list').innerHTML = rows.length ?
    '<table><tr><th>Artifact</th><th>Type</th><th>Status</th><th>Trust</th>' +
    '<th>Quarantine</th><th></th></tr>' + rows.map(a =>
      `<tr><td><small>${esc(a.artifact_id.slice(0, 8))}</small></td>
       <td>${esc(a.artifact_type)}</td>
       <td><b>${esc(a.artifact_status)}</b></td>
       <td>${esc(a.artifact_trust_tier)}</td>
       <td>${esc(a.quarantine_status)}</td>
       <td><button onclick="openArtifact('${esc(a.artifact_id)}')">Open
       </button></td></tr>`).join('') + '</table>'
    : '<i>No artifacts yet.</i>';
};

window.openArtifact = async (id) => {
  const a = await get('/ai-artifacts/' + id);
  const claims = await get('/ai-artifacts/' + id + '/claims');
  const vs = await get('/ai-artifacts/' + id + '/versions');
  $('artifact-detail').innerHTML = `
    <h3>Artifact ${esc(id.slice(0, 8))}
      <span class="badge">${esc(a.artifact_status)}</span></h3>
    <p><b>type</b> ${esc(a.artifact_type)} · <b>trust</b>
      ${esc(a.artifact_trust_tier)} · <b>version</b>
      ${esc(String(a.artifact_version))} · <b>quarantine</b>
      ${esc(a.quarantine_status)}</p>
    <p><b>state_hash</b> <code>${esc((a.artifact_state_hash
      || '').slice(0, 14))}…</code> · <b>content_hash</b>
      <code>${esc((a.artifact_content_hash || '').slice(0, 14))}…</code></p>
    <p><b>manifest_hash</b> <code>${esc((a.artifact_manifest_hash
      || '').slice(0, 14))}…</code> · <b>claim_graph_hash</b>
      <code>${esc((a.artifact_claim_graph_hash || '').slice(0, 14))}…</code></p>
    <p><button onclick="verifyArtifact('${esc(id)}')">Verify</button>
      <button onclick="materializeArtifact('${esc(id)}')">Materialization-check
      </button> <span id="artifact-msg"></span></p>
    <h4>Claims (${claims.claim_graph.claims.length})</h4>
    <table><tr><th>Predicate</th><th>Subject</th><th>Support</th></tr>
      ${claims.claim_graph.claims.map(cl => `<tr>
        <td>${esc(String(cl.claim_predicate))}</td>
        <td>${esc(String(cl.claim_subject_id))}</td>
        <td>${esc(cl.claim_support_status)}</td></tr>`).join('')}</table>
    <h4>Versions (${vs.versions.length})</h4>
    <table><tr><th>#</th><th>Status</th><th>Content hash</th></tr>
      ${vs.versions.map(v => `<tr><td>${esc(String(v.version_number))}</td>
        <td>${esc(v.version_status)}</td>
        <td><code>${esc((v.content_hash || '').slice(0, 12))}…</code></td>
        </tr>`).join('')}</table>
    <ul>${(a.honesty_labels || []).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>`;
};

window.verifyArtifact = async (id) => {
  const {data} = await send('POST', '/ai-artifacts/' + id + '/verify', {});
  $('artifact-msg').innerHTML =
    `verify <b class="${data.verification_status === 'MATCHED' ? 'ok'
      : 'err'}">${esc(data.verification_status)}</b> (tamper:
     ${data.tamper_detected})`;
};
window.materializeArtifact = async (id) => {
  const {data} = await send('POST',
    '/ai-artifacts/' + id + '/materialization-check', {});
  $('artifact-msg').innerHTML = `materialization
    <b>${esc(data.materialization_status)}</b> (can_execute_now:
    ${data.can_execute_now})`;
};
"""

TOOLS_SECTIONS = """
<section id="tools-section"><h2>Zero-Trust Tool Capability Registry</h2>
<ul class="labels"><small>
<li>This is a tool capability registry, not a Tool Broker.</li>
<li>Registering a tool descriptor does not execute the tool.</li>
<li>There is no execute endpoint and no dry-run execution in this mission.</li>
<li>The registry calls no external provider, no LLM and no MCP server.</li>
<li>The registry sends no customer message, moves no payment and writes no CRM.</li>
<li>The registry rewrites no evidence and exports no document.</li>
<li>Admission means a FUTURE broker may consider the tool; nothing runs it here.</li>
<li>Tool descriptor content is untrusted and can carry tool-poisoning; it never changes server policy.</li>
<li>Admission is fail-closed: any hard-fail signal blocks admission.</li>
<li>A forbidden capability can never be admitted, only recorded and blocked.</li>
<li>Consent requirements declared as non-overridable can never be downgraded.</li>
<li>Server-side tool-governance truth is authoritative over declared claims.</li>
<li>This is not production autonomous tool execution.</li>
</small></ul>
<div id="tools-list"><i>Loading tool registry…</i></div>
<div id="tool-detail"></div>
</section>
"""

TOOLS_JS = """
window.loadToolsSection = async (me) => { await loadTools(); };

window.loadTools = async () => {
  let rows; try { rows = await get('/ai-tools'); }
  catch (e) { $('tools-list').innerHTML =
    '<i>Tool registry is not available for your role.</i>'; return; }
  $('tools-list').innerHTML = rows.length ?
    '<table><tr><th>Tool</th><th>Category</th><th>Side effect</th>' +
    '<th>Risk</th><th>Status</th><th>Quarantine</th><th></th></tr>' +
    rows.map(t =>
      `<tr><td>${esc(t.tool_name)} <small>(${esc(t.tool_key)})</small></td>
       <td>${esc(t.category)}</td>
       <td>${esc(t.side_effect_class)}</td>
       <td>${esc(t.risk_class)}</td>
       <td><b>${esc(t.status)}</b></td>
       <td>${esc(t.quarantine_status)}</td>
       <td><button onclick="openTool('${esc(t.tool_id)}')">Open</button></td>
       </tr>`).join('') + '</table>'
    : '<i>No tools registered yet.</i>';
};

window.openTool = async (id) => {
  const t = await get('/ai-tools/' + id);
  const pol = await get('/ai-tools/' + id + '/policy');
  const neg = await get('/ai-tools/' + id + '/negative-capabilities');
  const inv = pol.invariant_matrix;
  $('tool-detail').innerHTML = `
    <h3>${esc(t.tool_name)}
      <span class="badge">${esc(t.status)}</span></h3>
    <p><b>category</b> ${esc(t.category)} · <b>side effect</b>
      ${esc(t.side_effect_class)} · <b>risk</b> ${esc(t.risk_class)} ·
      <b>trust</b> ${esc(t.trust_tier)} · <b>admitted</b>
      ${esc(String(t.admitted))}</p>
    <p><b>state_hash</b> <code>${esc((t.tool_state_hash
      || '').slice(0, 14))}…</code> · <b>descriptor_hash</b>
      <code>${esc((t.descriptor_hash || '').slice(0, 14))}…</code></p>
    <p><b>hard-fail signals</b>
      ${(t.hard_fail_signals || []).map(s =>
        `<span class="err">${esc(s)}</span>`).join(' ') || '<i>none</i>'}</p>
    <p><button onclick="admitTool('${esc(id)}')">Admit</button>
      <button onclick="verifyTool('${esc(id)}')">Verify</button>
      <button onclick="driftTool('${esc(id)}')">Drift-check</button>
      <span id="tool-msg"></span></p>
    <h4>Security invariants</h4>
    <table><tr><th>Invariant</th><th>Holds</th></tr>
      ${Object.entries(inv.results).map(([k, v]) => `<tr><td>${esc(k)}</td>
        <td class="${v ? 'ok' : 'err'}">${esc(String(v))}</td></tr>`).join('')}
    </table>
    <h4>Negative capabilities</h4>
    <p>${neg.negative_capabilities.all_hold ?
      '<b class="ok">all hold</b>' :
      '<b class="err">violated: ' +
      esc(neg.negative_capabilities.violated.join(', ')) + '</b>'}</p>
    <ul>${(t.honesty_labels || []).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>`;
};

window.admitTool = async (id) => {
  const {data} = await send('POST', '/ai-tools/' + id + '/admit', {});
  $('tool-msg').innerHTML = `admission <b class="${data.admitted ? 'ok'
    : 'err'}">${esc(data.admission_status)}</b>`;
  await loadTools();
};
window.verifyTool = async (id) => {
  const {data} = await send('POST', '/ai-tools/' + id + '/verify', {});
  $('tool-msg').innerHTML = `verify <b class="${data.verification_status
    === 'MATCHED' ? 'ok' : 'err'}">${esc(data.verification_status)}</b>
    (tamper: ${data.tamper_detected})`;
};
window.driftTool = async (id) => {
  const {data} = await send('POST', '/ai-tools/' + id + '/drift-check', {});
  $('tool-msg').innerHTML =
    `drift <b>${esc(data.supply_chain.verdict)}</b>`;
};
"""

QUALITY_SECTIONS = """
<section id="tool-quality-section"><h2>Tool Descriptor Quality Gate</h2>
<ul class="labels"><small>
<li>Tool Description Quality Gate does not execute tools.</li>
<li>Quality pass does not mean executable.</li>
<li>Future Tool Broker is still required.</li>
<li>Quality scoring is deterministic and local; it does not use LLM.</li>
<li>Formal descriptor IR is deterministic and limited; it is not full semantic understanding.</li>
<li>Assurance graph is local evidence, not production certification.</li>
<li>Mutation harness is deterministic and limited; it does not prove full paraphrase robustness.</li>
<li>Metamorphic tests are deterministic and limited; they do not prove complete semantic safety.</li>
<li>Prompt-context recommendation is future-readiness metadata only.</li>
<li>Quality pass cannot override TOOL-B1 security blockers.</li>
<li>Server-side registry truth is authoritative.</li>
</small></ul>
<div id="tool-quality-list"><i>Loading tool quality…</i></div>
<div id="tool-quality-detail"></div>
</section>
"""

QUALITY_JS = """
window.loadQualitySection = async (me) => { await loadQuality(); };

window.loadQuality = async () => {
  let data; try { data = await get('/ai-tools/registry/quality'); }
  catch (e) { $('tool-quality-list').innerHTML =
    '<i>Tool quality is not available for your role.</i>'; return; }
  const rows = data.summaries || [];
  $('tool-quality-list').innerHTML = rows.length ?
    '<table><tr><th>Tool</th><th>Quality status</th><th>Score</th><th></th></tr>'
    + rows.map(r => `<tr><td><small>${esc(r.tool_id.slice(0,8))}</small></td>
       <td><b>${esc(r.quality_status)}</b></td>
       <td>${esc(String(r.quality_score_total))}</td>
       <td><button onclick="openQuality('${esc(r.tool_id)}')">Open</button>
       </td></tr>`).join('') + '</table>'
    : '<i>No quality reports yet — run a quality check on a tool.</i>';
};

window.runQualityCheck = async (id) => {
  const {data} = await send('POST', '/ai-tools/' + id + '/quality/check', {});
  await loadQuality();
  await openQuality(id);
};

window.openQuality = async (id) => {
  let rep; try { rep = await get('/ai-tools/' + id + '/quality'); }
  catch (e) {
    $('tool-quality-detail').innerHTML =
      `<p><button onclick="runQualityCheck('${esc(id)}')">Run quality check
       </button> <i>no report yet</i></p>`; return; }
  const ir = rep.formal_descriptor_ir, g = rep.descriptor_assurance_graph;
  const b = rep.planner_selection_boundary, c = rep.planner_confusion_matrix;
  $('tool-quality-detail').innerHTML = `
    <h3>Quality ${esc(id.slice(0,8))}
      <span class="badge">${esc(rep.quality_status)}</span></h3>
    <p><b>score</b> ${esc(String(rep.quality_score_total))} · <b>safety</b>
      ${esc(String(rep.descriptor_safety_score))} · <b>dominant blocker</b>
      ${esc(String(rep.dominant_blocker_category))}
      <button onclick="runQualityCheck('${esc(id)}')">Re-check</button>
      <button onclick="verifyQuality('${esc(id)}')">Verify</button>
      <span id="tool-quality-msg"></span></p>
    <h4>Blockers (${rep.quality_blockers.length})</h4>
    <ul>${rep.quality_blockers.map(x =>
      `<li class="err">${esc(x.code)} — <small>${esc(x.detail)}</small></li>`)
      .join('') || '<li><i>none</i></li>'}</ul>
    <h4>Warnings (${rep.quality_warnings.length})</h4>
    <ul>${rep.quality_warnings.map(x =>
      `<li>${esc(x.code)}</li>`).join('') || '<li><i>none</i></li>'}</ul>
    <h4>Formal descriptor IR</h4>
    <p><b>category guess</b> ${esc(ir.ir_category_guess)} · <b>side-effect</b>
      ${esc(ir.ir_side_effect_guess)} · <b>risk</b> ${esc(ir.ir_risk_guess)} ·
      <b>matches registry</b>
      <span class="${ir.ir_matches_tool_b1_truth ? 'ok' : 'err'}">
      ${esc(String(ir.ir_matches_tool_b1_truth))}</span></p>
    <h4>Assurance graph</h4>
    <p><b>status</b> ${esc(g.assurance_graph_status)} · <b>acyclic</b>
      ${esc(String(g.acyclic))} · <b>unsupported claims</b>
      ${esc(String(g.unsupported_claims.length))}</p>
    <h4>Planner selection boundary</h4>
    <p><b>minimal context</b> <b class="${b.minimal_context_status
      === 'NEVER_EXPOSE' ? 'err' : 'ok'}">${esc(b.minimal_context_status)}</b>
      · <b>budget</b> ${esc(String(b.context_exposure_budget))}</p>
    <h4>Planner confusion / misrouting</h4>
    <p><b>misrouting risk</b> ${esc(String(c.misrouting_risk))} ·
      <b>counterfactual misrouting</b>
      ${esc(String(rep.counterfactual_planner.misrouting_detected))}</p>
    <h4>Robustness</h4>
    <p><b>mutation</b> ${esc(rep.mutation_test_summary.status)} ·
      <b>metamorphic</b> ${esc(rep.metamorphic_test_summary.status)} ·
      <b>monotonic risk</b> ${esc(rep.monotonic_risk_summary.monotonicity_status)}
      · <b>non-regression</b>
      ${esc(rep.non_regression_summary.non_regression_status)}</p>
    <ul>${(rep.honesty_labels || []).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>`;
};

window.verifyQuality = async (id) => {
  const {data} = await send('POST', '/ai-tools/' + id + '/quality/verify', {});
  $('tool-quality-msg').innerHTML = `verify <b class="${
    data.verification_status === 'MATCHED' ? 'ok' : 'err'}">${
    esc(data.verification_status)}</b>`;
};
"""

CONTRACTS_SECTIONS = """
<section id="tool-contracts-section"><h2>Protocol Contract Proof Kernel</h2>
<ul class="labels"><small>
<li>This is an internal contract only.</li>
<li>This is not an MCP server or client.</li>
<li>This contract does not execute tools.</li>
<li>Projection does not mean runtime compliance.</li>
<li>Broker-readiness certificate does not execute or approve tools.</li>
<li>Future Tool Broker is still required before any tool call.</li>
<li>No external provider is called.</li>
<li>No token is issued.</li>
<li>Sampling, elicitation, resources and prompts are not implemented in this mission.</li>
<li>Runtime capabilities are denied in TOOL-B3.</li>
<li>Effect-trace semantics are future-readiness metadata only; no runtime effects are observed in B3.</li>
<li>Contract compatibility does not mean production protocol compliance.</li>
<li>Server-side registry truth is authoritative.</li>
</small></ul>
<div id="tool-contracts-list"><i>Loading contracts…</i></div>
<div id="tool-contract-detail"></div>
</section>
"""

CONTRACTS_JS = """
window.loadContractsSection = async (me) => { await loadContracts(); };

window.loadContracts = async () => {
  let data; try { data = await get('/ai-tools/registry/contracts'); }
  catch (e) { $('tool-contracts-list').innerHTML =
    '<i>Tool contracts are not available for your role.</i>'; return; }
  const rows = data.summaries || [];
  $('tool-contracts-list').innerHTML = rows.length ?
    '<table><tr><th>Contract</th><th>Tool</th><th>Status</th><th></th></tr>' +
    rows.map(r => `<tr><td><small>${esc(r.contract_id.slice(0,8))}</small></td>
       <td><small>${esc(r.tool_id.slice(0,8))}</small></td>
       <td><b>${esc(r.contract_status)}</b></td>
       <td><button onclick="openContract('${esc(r.tool_id)}','${esc(
         r.contract_id)}')">Open</button></td></tr>`).join('') + '</table>'
    : '<i>No contracts yet — create one from an admitted, quality-passed tool.</i>';
};

window.openContract = async (toolId, cid) => {
  const base = '/ai-tools/' + toolId + '/contracts/' + cid;
  const c = await get(base);
  let proj = null;
  try { proj = await get(base + '/proof-bundle'); } catch (e) {}
  let cert = null;
  try { cert = await get(base + '/broker-readiness'); } catch (e) {}
  const et = c.effect_trace_semantics, dg = c.runtime_capability_deny_graph;
  const sb = c.contract_scope_binding, eb = c.contract_effect_boundary;
  $('tool-contract-detail').innerHTML = `
    <h3>Contract ${esc(cid.slice(0,8))}
      <span class="badge">${esc(c.contract_status)}</span></h3>
    <p><b>risk</b> ${esc(c.contract_risk_class)} · <b>side effect</b>
      ${esc(c.contract_side_effect_class)} · <b>future broker required</b>
      ${esc(String(c.requires_future_tool_broker))}
      <button onclick="verifyContract('${esc(toolId)}','${esc(cid)}')">Verify
      </button>
      <button onclick="projectContract('${esc(toolId)}','${esc(cid)}')">
      Project MCP-like</button> <span id="tool-contract-msg"></span></p>
    <p><b>contract_hash</b> <code>${esc((c.contract_hash||'').slice(0,14))}…
      </code> · <b>ABI</b> <code>${esc((c.contract_abi.abi_hash||'').slice(
        0,14))}…</code></p>
    <p><b>blockers</b> ${(c.contract_blockers||[]).map(b =>
      `<span class="err">${esc(b)}</span>`).join(' ') || '<i>none</i>'}</p>
    <h4>Effect-trace semantics</h4>
    <p><b>allowed</b> ${esc((et.allowed_effects||[]).join(', ') || 'none')} ·
      <b>forbidden</b> ${esc(String((et.forbidden_effects||[]).length))} ·
      <b>status</b> ${esc(et.effect_trace_status)}</p>
    <h4>Runtime capability deny graph</h4>
    <p><b>denied</b> ${esc(String((dg.denied_capabilities||[]).length))}
      capabilities · <b>status</b> ${esc(dg.deny_graph_status)}</p>
    <h4>Effect boundary</h4>
    <p><b>read-only mislabel</b> <b class="${eb.read_only_mislabel_detected
      ? 'err' : 'ok'}">${esc(String(eb.read_only_mislabel_detected))}</b> ·
      <b>future broker required</b>
      ${esc(String(eb.future_tool_broker_required))}</p>
    <h4>Scope binding</h4>
    <p><b>cross-tenant allowed</b>
      <b class="${sb.cross_tenant_allowed ? 'err' : 'ok'}">${esc(String(
        sb.cross_tenant_allowed))}</b> · <b>scope expansion</b>
      ${esc(String(sb.scope_expansion_detected))}</p>
    <h4>Proof bundle / broker-readiness</h4>
    <p><b>proof bundle</b> ${proj ? esc(
      proj.contract_proof_bundle.proof_bundle_status) : 'n/a'} ·
      <b>certificate</b> ${cert ? esc(
        cert.broker_readiness_certificate.certificate_status) : 'n/a'}</p>
    <ul>${(c.honesty_labels||[]).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>`;
};

window.verifyContract = async (toolId, cid) => {
  const {data} = await send('POST',
    '/ai-tools/' + toolId + '/contracts/' + cid + '/verify', {});
  $('tool-contract-msg').innerHTML = `verify <b class="${
    data.verification_status === 'MATCHED' ? 'ok' : 'err'}">${
    esc(data.verification_status)}</b>`;
};
window.projectContract = async (toolId, cid) => {
  const {data} = await send('POST',
    '/ai-tools/' + toolId + '/contracts/' + cid + '/project',
    {target: 'MCP_LIKE_TOOL_DESCRIPTOR'});
  $('tool-contract-msg').innerHTML = `projection <b>${esc(
    data.projection_status)}</b>`;
};
"""

ACTIONS_SECTIONS = """
<section id="tool-actions-section"><h2>Causal Pre-Action Reference Monitor</h2>
<ul class="labels"><small>
<li>The pre-action monitor executes nothing.</li>
<li>A pre-action decision is not an execution.</li>
<li>ALLOWED_FOR_FUTURE_BROKER_ONLY does not run any tool.</li>
<li>A future Tool Broker is required and does not exist yet.</li>
<li>An Action Passport is not a token and confers no authority.</li>
<li>A Governance Receipt is not authority.</li>
<li>A Future Execution Lease is a NOT_IMPLEMENTED placeholder.</li>
<li>The AI cannot approve its own action or self-validate as human truth.</li>
<li>Consent is non-overridable; nondelegable decisions are human-only.</li>
<li>No token is issued; no external provider is called; no payment moves.</li>
<li>Registry, quality and contract truth are authoritative and only narrow authority.</li>
</small></ul>
<div id="tool-actions-summary"><i>Loading pre-action monitor…</i></div>
<div id="tool-actions-list"></div>
</section>
"""

ACTIONS_JS = """
window.loadActionsSection = async (me) => { await loadActions(); };

window.loadActions = async () => {
  let reg; try { reg = await get('/ai-tools/actions/registry'); }
  catch (e) { $('tool-actions-summary').innerHTML =
    '<i>The pre-action monitor is not available for your role.</i>'; return; }
  $('tool-actions-summary').innerHTML =
    `<p><b>proposals</b> ${esc(String(reg.proposal_count))} ·
      <b>decisions</b> ${esc(String(reg.decision_count))}</p>` +
    '<p><small>' + Object.entries(reg.decisions_by_status || {}).map(
      ([k, v]) => `${esc(k)}: <b>${esc(String(v))}</b>`).join(' · ') + '</small></p>';
  let props = []; try { props = await get('/ai-tools/actions/proposals'); }
  catch (e) {}
  $('tool-actions-list').innerHTML = (props.length ?
    '<table><tr><th>Proposal</th><th>Tool</th><th>Action</th><th></th></tr>' +
    props.map(p => `<tr><td><small>${esc(p.proposal_envelope_id.slice(0,8))}
       </small></td><td><small>${esc((p.tool_id||'').slice(0,8))}</small></td>
       <td><small>${esc(p.action_path||'')}</small></td>
       <td><button onclick="openDecision('${esc(p.proposal_envelope_id)}')">
       Decision</button></td></tr>`).join('') + '</table>'
    : '<i>No action proposals yet.</i>');
};

window.openDecision = async (pid) => {
  const base = '/ai-tools/actions/proposals/' + pid;
  const d = await get(base + '/decision');
  let vr = null; try { vr = (await send('POST', base + '/verify', {})).data; }
  catch (e) {}
  const passport = d.action_passport || {}, lease = d.future_execution_lease || {};
  $('tool-actions-list').innerHTML = `
    <h3>Decision for ${esc(pid.slice(0,8))}
      <span class="badge">${esc(d.decision_status)}</span></h3>
    <p><b>dominant signal</b> ${esc(d.dominant_signal)} ·
      <b>reason</b> <small>${esc(d.dominant_reason_code)}</small></p>
    <p><b>executes nothing</b> <b class="ok">${esc(String(d.executes_nothing))}
      </b> · <b>future broker required</b>
      ${esc(String(d.requires_future_tool_broker))}</p>
    <p><b>passport is token</b> <b class="ok">${esc(String(
      passport.is_token))}</b> · <b>lease</b> ${esc(lease.lease_status)}</p>
    <p><b>signals</b> ${(d.all_signals||[]).map(s =>
      `<span class="err">${esc(s)}</span>`).join(' ') || '<i>none</i>'}</p>
    <p><b>decision hash</b> <code>${esc((d.decision_hash||'').slice(0,14))}…
      </code> · <b>verify</b> ${vr ? `<b class="${
        vr.decision_hash_valid ? 'ok' : 'err'}">${esc(vr.verification_status)}
      </b>` : 'n/a'}</p>
    <ul>${(d.honesty_labels||[]).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>
    <button onclick="loadActions()">← back</button>`;
};
"""

BROKER_SECTIONS = """
<section id="tool-broker-section"><h2>Four-Plane Proof-Carrying Null Broker</h2>
<ul class="labels"><small>
<li>NULL_EFFECT_ONLY — this broker executes nothing.</li>
<li>NO_REAL_EXECUTION — no tool run, no external provider, no MCP runtime.</li>
<li>VALIDATION_ONLY / FUTURE_RUNTIME_PLACEHOLDER.</li>
<li>PROOF_CARRYING_NULL_BROKER_ONLY / FOUR_PLANE_BROKER_INTEGRITY_ONLY.</li>
<li>CREDENTIAL_FREE_CORRIDOR_ONLY — no credential, no token, no secret.</li>
<li>ADVERSARIALLY_VERIFIED_NULL_ONLY — fails closed under fault injection.</li>
<li>An Action Passport, Governance Receipt, Proof-Carrying Certificate and Negative Execution Certificate are evidence only, never execution authority or tokens.</li>
<li>The only effector is a null effector; its outcome is NO_EFFECT_OUTCOME.</li>
<li>No null output leaks payload, secrets, credentials, approval/consent artifacts or customer data.</li>
<li>Server-side B1/B2/B3/B4 truth is authoritative and only narrows authority.</li>
</small></ul>
<div id="tool-broker-summary"><i>Loading null broker…</i></div>
<div id="tool-broker-list"></div>
</section>
"""

BROKER_JS = """
window.loadBrokerSection = async (me) => { await loadBroker(); };

window.loadBroker = async () => {
  let reg; try { reg = await get('/ai-tools/broker/registry'); }
  catch (e) { $('tool-broker-summary').innerHTML =
    '<i>The null broker is not available for your role.</i>'; return; }
  $('tool-broker-summary').innerHTML =
    `<p><b>requests</b> ${esc(String(reg.broker_request_count))} ·
      <b>outcomes</b> ${esc(String(reg.broker_outcome_count))}</p>` +
    '<p><small>' + Object.entries(reg.outcomes_by_status || {}).map(
      ([k, v]) => `${esc(k)}: <b>${esc(String(v))}</b>`).join(' · ') + '</small></p>';
  let reqs = []; try { reqs = await get('/ai-tools/broker/requests'); }
  catch (e) {}
  $('tool-broker-list').innerHTML = (reqs.length ?
    '<table><tr><th>Request</th><th>Tool</th><th></th></tr>' +
    reqs.map(r => `<tr><td><small>${esc((r.broker_request_envelope_id||'').slice(0,8))}
       </small></td><td><small>${esc((r.tool_id||'').slice(0,8))}</small></td>
       <td><button onclick="openBrokerOutcome('${esc(r.broker_request_envelope_id)}')">
       Outcome</button></td></tr>`).join('') + '</table>'
    : '<i>No broker requests yet.</i>');
};

window.openBrokerOutcome = async (rid) => {
  const base = '/ai-tools/broker/requests/' + rid;
  const o = await get(base + '/outcome');
  let vr = null; try { vr = (await send('POST', base + '/verify', {})).data; }
  catch (e) {}
  const gate = o.broker_release_gate_report || {};
  const har = o.fault_injection_harness || {};
  const nx = o.null_output_non_exfiltration || {};
  $('tool-broker-list').innerHTML = `
    <h3>Broker outcome ${esc(rid.slice(0,8))}
      <span class="badge">${esc(o.broker_status)}</span></h3>
    <p><b>dominant</b> ${esc(o.dominant_signal)} ·
      <b>reason</b> <small>${esc(o.dominant_reason_code)}</small></p>
    <p><b>effect</b> <b class="ok">${esc(o.effect_outcome)}</b> ·
      <b>executes nothing</b> <b class="ok">${esc(String(o.executes_nothing))}</b>
      · <b>future runtime required</b> ${esc(String(o.requires_future_runtime))}</p>
    <p><b>release gate</b> <b class="${gate.release_gate_status ===
      'RELEASE_GATE_PASSED' ? 'ok' : 'err'}">${esc(gate.release_gate_status)}</b>
      · <b>fault injection</b> ${esc(har.harness_status)}
      (${esc(String((har.fault_cases||[]).length))} cases,
      ${esc(String((har.unexpected_positive_results||[]).length))} unexpected)</p>
    <p><b>null-output non-exfiltration</b> <b class="${nx.leak_detected ?
      'err' : 'ok'}">${esc(nx.non_exfiltration_status)}</b></p>
    <p><b>decision hash</b> <code>${esc((o.broker_decision_hash||'').slice(0,14))}…
      </code> · <b>verify</b> ${vr ? `<b class="${vr.broker_decision_hash_valid ?
        'ok' : 'err'}">${esc(vr.verification_status)}</b>` : 'n/a'}</p>
    <p><b>signals</b> ${(o.all_signals||[]).map(s =>
      `<span class="err">${esc(s)}</span>`).join(' ') || '<i>none</i>'}</p>
    <ul>${(o.honesty_labels||[]).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>
    <button onclick="loadBroker()">← back</button>`;
};
"""

RUNTIME_SECTIONS = """
<section id="tool-runtime-section"><h2>Verifiable Read-Path Runtime Microkernel</h2>
<ul class="labels"><small>
<li>READ_ONLY_INTERNAL_RUNTIME_ONLY — local, deterministic, read-only.</li>
<li>SNAPSHOT_BOUND_ONLY / TEMPORAL_SNAPSHOT_ISOLATED — reads only frozen local snapshots.</li>
<li>SEMANTIC_READ_FIREWALL_PASSED / READ_SET_ATTESTED.</li>
<li>OUTPUT_PROVENANCE_BISIMULATED — every safe output field traces to an attested read.</li>
<li>CANARY_NON_LEAKAGE_PROVED — no synthetic canary leaks to output.</li>
<li>INFORMATION_BUDGET_ENFORCED / READ_AMPLIFICATION_GUARDED / SIDE_CHANNEL_BUDGET_SEALED.</li>
<li>DATA_DIODE_OUTPUT_ONLY / DETERMINISM_ENTROPY_SEALED / DETERMINISTIC_REPLAY_REQUIRED.</li>
<li>NO_NETWORK / NO_PROVIDER / NO_TOKEN / NO_CREDENTIAL / NO_SECRET_READ / NO_WRITE_EFFECT.</li>
<li>NO_MUTABLE_PRODUCTION_READ / NOT_PRODUCTION_AUTONOMOUS_EXECUTION.</li>
<li>No OS-level sandbox or differential privacy is claimed.</li>
</small></ul>
<div id="tool-runtime-summary"><i>Loading read-path runtime…</i></div>
<div id="tool-runtime-list"></div>
</section>
"""

RUNTIME_JS = """
window.loadRuntimeSection = async (me) => { await loadRuntime(); };

window.loadRuntime = async () => {
  let reg; try { reg = await get('/ai-tools/runtime/registry'); }
  catch (e) { $('tool-runtime-summary').innerHTML =
    '<i>The read-path runtime is not available for your role.</i>'; return; }
  $('tool-runtime-summary').innerHTML =
    `<p><b>requests</b> ${esc(String(reg.runtime_request_count))} ·
      <b>outcomes</b> ${esc(String(reg.runtime_outcome_count))} ·
      <b>snapshots</b> ${esc(String(reg.snapshot_count))}</p>` +
    '<p><small>' + Object.entries(reg.outcomes_by_status || {}).map(
      ([k, v]) => `${esc(k)}: <b>${esc(String(v))}</b>`).join(' · ') + '</small></p>';
  let reqs = []; try { reqs = await get('/ai-tools/runtime/requests'); }
  catch (e) {}
  $('tool-runtime-list').innerHTML = (reqs.length ?
    '<table><tr><th>Request</th><th>Snapshot</th><th></th></tr>' +
    reqs.map(r => `<tr><td><small>${esc((r.runtime_request_id||'').slice(0,8))}
       </small></td><td><small>${esc((r.snapshot_id||'').slice(0,8))}</small></td>
       <td><button onclick="openRuntimeOutcome('${esc(r.runtime_request_id)}')">
       Outcome</button></td></tr>`).join('') + '</table>'
    : '<i>No runtime requests yet.</i>');
};

window.openRuntimeOutcome = async (rid) => {
  const base = '/ai-tools/runtime/requests/' + rid;
  const o = await get(base + '/outcome');
  let vr = null; try { vr = (await send('POST', base + '/verify', {})).data; }
  catch (e) {}
  const gate = o.runtime_release_gate_report || {};
  const bis = o.output_provenance_bisimulation || {};
  const can = o.canary_non_leakage_proof || {};
  const ni = o.semantic_non_interference_matrix || {};
  $('tool-runtime-list').innerHTML = `
    <h3>Runtime outcome ${esc(rid.slice(0,8))}
      <span class="badge">${esc(o.runtime_status)}</span></h3>
    <p><b>decision</b> ${esc(o.runtime_decision_status)} ·
      <b>kind</b> ${esc(o.runtime_outcome_kind)} ·
      <b>reason</b> <small>${esc(o.dominant_reason_code)}</small></p>
    <p><b>read-only</b> <b class="ok">${esc(String(o.read_only))}</b> ·
      <b>external effect</b> <b class="ok">${esc(String(
        o.produced_external_effect))}</b> ·
      <b>data diode</b> ${esc(o.data_diode_status)}</p>
    <p><b>bisimulation</b> <b class="${bis.bisimulation_status ===
      'BISIMULATION_MATCHED' ? 'ok' : 'err'}">${esc(bis.bisimulation_status)}</b>
      · <b>non-interference</b> ${esc(ni.matrix_status)}
      · <b>canary</b> <b class="${can.leak_detected ? 'err' : 'ok'}">${esc(
        can.proof_status)}</b></p>
    <p><b>release gate</b> <b class="${gate.release_gate_status ===
      'RELEASE_GATE_PASSED' ? 'ok' : 'err'}">${esc(gate.release_gate_status)}</b>
      · <b>safe output</b> <code>${esc(JSON.stringify(
        o.safe_output || {}).slice(0,60))}</code></p>
    <p><b>decision hash</b> <code>${esc((o.runtime_decision_hash||'').slice(
      0,14))}…</code> · <b>verify</b> ${vr ? `<b class="${
        vr.runtime_decision_hash_valid ? 'ok' : 'err'}">${esc(
        vr.verification_status)}</b>` : 'n/a'}</p>
    <p><b>signals</b> ${(o.all_signals||[]).map(s =>
      `<span class="err">${esc(s)}</span>`).join(' ') || '<i>none</i>'}</p>
    <ul>${(o.honesty_labels||[]).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>
    <button onclick="loadRuntime()">← back</button>`;
};
"""

WRITE_INTENT_SECTIONS = """
<section id="tool-write-intent-section"><h2>Transaction-Escrow Write-Intent Draft Runtime</h2>
<ul class="labels"><small>
<li>WRITE_INTENT_DRAFT_ONLY / SEMANTIC_TRANSACTION_DRAFT_ONLY — models a FUTURE write; never executes.</li>
<li>TRANSACTION_ESCROW_ONLY / COMMIT_READINESS_ESCROW_ONLY — escrow is local evidence, not executable.</li>
<li>FUTURE_COMMIT_GATE_PLACEHOLDER_ONLY — no commit endpoint exists.</li>
<li>SEMANTIC_ROLLBACK_ATTACK_FENCE_REQUIRED — action replay and authority resurrection are blocked.</li>
<li>CONCURRENT_DRAFT_CONFLICT_CHECKED — conflicting drafts cannot both become future-ready.</li>
<li>STAGED_EFFECT_OUTBOX_PLACEHOLDER_ONLY — every staged effect is quarantined and unreleasable.</li>
<li>HUMAN_APPROVAL_REQUIRED_BEFORE_FUTURE_COMMIT / MEANINGFUL_HUMAN_JUDGMENT_REQUIRED / APPROVAL_DOES_NOT_EXECUTE.</li>
<li>NO_REAL_WRITE_EFFECT / NO_EFFECT_RELEASE / NO_COMMIT_ACTIVATION / NO_PAYMENT / NO_CRM_MUTATION / NO_EVIDENCE_MUTATION / NO_DATA_EXPORT.</li>
<li>NO_EXTERNAL_PROVIDER / NO_NETWORK / NO_TOKEN / NO_CREDENTIAL / NOT_PRODUCTION_AUTONOMOUS_EXECUTION.</li>
</small></ul>
<div id="tool-write-intent-summary"><i>Loading write-intent draft runtime…</i></div>
<div id="tool-write-intent-list"></div>
</section>
"""

WRITE_INTENT_JS = """
window.loadWriteIntentSection = async (me) => { await loadWriteIntent(); };

window.loadWriteIntent = async () => {
  let reg; try { reg = await get('/ai-tools/write-intents/registry'); }
  catch (e) { $('tool-write-intent-summary').innerHTML =
    '<i>The write-intent draft runtime is not available for your role.</i>'; return; }
  $('tool-write-intent-summary').innerHTML =
    `<p><b>requests</b> ${esc(String(reg.write_intent_request_count))} ·
      <b>outcomes</b> ${esc(String(reg.write_intent_outcome_count))}</p>` +
    '<p><small>' + Object.entries(reg.outcomes_by_status || {}).map(
      ([k, v]) => `${esc(k)}: <b>${esc(String(v))}</b>`).join(' · ') + '</small></p>';
  let reqs = []; try { reqs = await get('/ai-tools/write-intents'); }
  catch (e) {}
  $('tool-write-intent-list').innerHTML = (reqs.length ?
    '<table><tr><th>Write-intent</th><th>Target</th><th></th></tr>' +
    reqs.map(r => `<tr><td><small>${esc((r.write_intent_id||'').slice(0,8))}
       </small></td><td><small>${esc(r.target_entity_id||'')}</small></td>
       <td><button onclick="openWriteIntentOutcome('${esc(r.write_intent_id)}')">
       Outcome</button></td></tr>`).join('') + '</table>'
    : '<i>No write-intent drafts yet.</i>');
};

window.openWriteIntentOutcome = async (wid) => {
  const base = '/ai-tools/write-intents/' + wid;
  const o = await get(base + '/outcome');
  let vr = null; try { vr = (await send('POST', base + '/verify', {})).data; }
  catch (e) {}
  const gate = o.write_intent_release_gate_report || {};
  const cap = o.transaction_escrow_capsule || {};
  const cert = o.escrowed_commit_readiness_certificate || {};
  const oracle = o.transaction_conflict_oracle || {};
  const fence = o.semantic_rollback_fence || {};
  const rne = o.transaction_readiness_non_execution_certificate || {};
  $('tool-write-intent-list').innerHTML = `
    <h3>Write-intent outcome ${esc(wid.slice(0,8))}
      <span class="badge">${esc(o.write_intent_status)}</span></h3>
    <p><b>decision</b> ${esc(o.write_intent_decision_status)} ·
      <b>kind</b> ${esc(o.write_intent_outcome_kind)} ·
      <b>reason</b> <small>${esc(o.dominant_reason_code)}</small></p>
    <p><b>draft-only</b> <b class="ok">${esc(String(o.draft_only))}</b> ·
      <b>commit executable now</b> <b class="${o.commit_executable_now ? 'err' : 'ok'}">${esc(
        String(o.commit_executable_now))}</b> ·
      <b>ready for FUTURE commit only</b> ${esc(String(o.ready_for_future_commit_only))}</p>
    <p><b>escrow</b> <b class="${cap.escrow_status === 'ESCROWED' ? 'ok' : 'err'}">${esc(
      cap.escrow_status)}</b> · <b>immutable</b> ${esc(String(cap.escrow_mutable === false))}
      · <b>conflict oracle</b> <b class="${oracle.oracle_decision === 'NO_CONFLICT'
        ? 'ok' : 'err'}">${esc(oracle.oracle_decision)}</b></p>
    <p><b>rollback fence</b> <b class="${fence.fence_status === 'FENCED' ? 'ok' : 'err'}">${esc(
      fence.fence_status)}</b> · <b>readiness non-execution</b> <b class="${
      rne.all_negative_claims_hold ? 'ok' : 'err'}">${esc(rne.certificate_status)}</b>
      · <b>commit-readiness</b> ${esc(cert.readiness_status)}</p>
    <p><b>release gate</b> <b class="${gate.release_gate_status === 'PASSED'
      ? 'ok' : 'err'}">${esc(gate.release_gate_status)}</b>
      · <b>decision hash</b> <code>${esc((o.write_intent_decision_hash||'').slice(0,14))}…</code>
      · <b>verify</b> ${vr ? `<b class="${vr.write_intent_decision_hash_valid ? 'ok' : 'err'}">${
        esc(vr.verification_status)}</b>` : 'n/a'}</p>
    <p><b>signals</b> ${(o.all_signals||[]).map(s =>
      `<span class="err">${esc(s)}</span>`).join(' ') || '<i>none</i>'}</p>
    <ul>${(o.honesty_labels||[]).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>
    <button onclick="loadWriteIntent()">← back</button>`;
};
"""

COMMIT_SIM_SECTIONS = """
<section id="tool-commit-sim-section"><h2>Machine-Checkable Pre-B9 Assurance Envelope</h2>
<ul class="labels"><small>
<li>LOCAL_COMMIT_SIMULATION_ONLY / PRE_B9_ASSURANCE_ONLY — simulation-only; never a real commit.</li>
<li>MACHINE_CHECKABLE_EVIDENCE_ONLY / NON_DELEGABLE_ARTIFACT_SEAL — artifacts are evidence, never authority.</li>
<li>B9_REVALIDATION_REQUIRED — B9 must recompute every factor; B8 pre-authorizes nothing.</li>
<li>NO_REAL_COMMIT / NO_EFFECT_RELEASE / NO_COMMIT_ACTIVATION / NO_B9_ACTIVATION.</li>
<li>NO_EXTERNAL_PROVIDER / NO_NETWORK / NO_TOKEN / NO_CREDENTIAL / NO_PAYMENT / NO_CUSTOMER_MESSAGE.</li>
<li>NO_CRM_MUTATION / NO_EVIDENCE_MUTATION / NO_DATA_EXPORT.</li>
<li>NOT_PRODUCTION_READY / NOT_PRODUCTION_AUTONOMOUS_EXECUTION.</li>
</small></ul>
<div id="tool-commit-sim-summary"><i>Loading pre-B9 assurance envelope…</i></div>
<div id="tool-commit-sim-list"></div>
</section>
"""

COMMIT_SIM_JS = """
window.loadCommitSimSection = async (me) => { await loadCommitSim(); };

window.loadCommitSim = async () => {
  let reg; try { reg = await get('/ai-tools/commit-simulations/registry'); }
  catch (e) { $('tool-commit-sim-summary').innerHTML =
    '<i>The pre-B9 assurance envelope is not available for your role.</i>'; return; }
  $('tool-commit-sim-summary').innerHTML =
    `<p><b>requests</b> ${esc(String(reg.commit_simulation_request_count))} ·
      <b>outcomes</b> ${esc(String(reg.commit_simulation_outcome_count))}</p>` +
    '<p><small>' + Object.entries(reg.outcomes_by_status || {}).map(
      ([k, v]) => `${esc(k)}: <b>${esc(String(v))}</b>`).join(' · ') + '</small></p>';
  let reqs = []; try { reqs = await get('/ai-tools/commit-simulations'); }
  catch (e) {}
  $('tool-commit-sim-list').innerHTML = (reqs.length ?
    '<table><tr><th>Commit-sim</th><th>Write-intent</th><th></th></tr>' +
    reqs.map(r => `<tr><td><small>${esc((r.commit_simulation_id||'').slice(0,8))}
       </small></td><td><small>${esc((r.b7_write_intent_id||'').slice(0,8))}</small></td>
       <td><button onclick="openCommitSimOutcome('${esc(r.commit_simulation_id)}')">
       Outcome</button></td></tr>`).join('') + '</table>'
    : '<i>No commit simulations yet.</i>');
};

window.openCommitSimOutcome = async (sid) => {
  const base = '/ai-tools/commit-simulations/' + sid;
  const o = await get(base + '/outcome');
  let vr = null; try { vr = (await send('POST', base + '/verify', {})).data; }
  catch (e) {}
  const gate = o.commit_sim_release_gate_report || {};
  const env = o.assurance_envelope || {};
  const net = o.evidence_closure_net || {};
  const seal = o.non_delegable_artifact_seal || {};
  const fw = o.b9_firewall || {};
  const nct = o.no_commit_theorem || {};
  const ci = o.final_ci_gate || {};
  $('tool-commit-sim-list').innerHTML = `
    <h3>Commit-sim outcome ${esc(sid.slice(0,8))}
      <span class="badge">${esc(o.commit_simulation_status)}</span></h3>
    <p><b>decision</b> ${esc(o.commit_simulation_decision_status)} ·
      <b>kind</b> ${esc(o.commit_simulation_outcome_kind)} ·
      <b>reason</b> <small>${esc(o.dominant_reason_code)}</small></p>
    <p><b>simulation only</b> <b class="ok">${esc(String(o.simulation_only))}</b> ·
      <b>commit executable now</b> <b class="${o.commit_executable_now ? 'err' : 'ok'}">${esc(
        String(o.commit_executable_now))}</b> ·
      <b>B9 revalidation required</b> ${esc(String(o.b9_revalidation_required))}</p>
    <p><b>assurance envelope</b> <b class="${env.decision_status === 'VALID'
      ? 'ok' : 'err'}">${esc(env.decision_status)}</b> · <b>authority</b> ${esc(
      String(env.is_authority))} · <b>closure</b> <b class="${
      net.closure_status === 'CLOSED' ? 'ok' : 'err'}">${esc(net.closure_status)}</b></p>
    <p><b>artifact seal</b> <b class="${seal.seal_status === 'SEALED' ? 'ok' : 'err'}">${esc(
      seal.seal_status)}</b> · <b>B9 firewall</b> <b class="${
      fw.firewall_status === 'SEALED' ? 'ok' : 'err'}">${esc(fw.firewall_status)}</b>
      · <b>no-commit theorem</b> <b class="${nct.theorem_holds ? 'ok' : 'err'}">${esc(
        nct.theorem_status)}</b> · <b>final CI</b> ${esc(ci.gate_status)}</p>
    <p><b>release gate</b> <b class="${gate.release_gate_status === 'PASSED'
      ? 'ok' : 'err'}">${esc(gate.release_gate_status)}</b>
      · <b>decision hash</b> <code>${esc((o.commit_simulation_decision_hash||'').slice(0,14))}…</code>
      · <b>verify</b> ${vr ? `<b class="${vr.commit_simulation_decision_hash_valid ? 'ok' : 'err'}">${
        esc(vr.verification_status)}</b>` : 'n/a'}</p>
    <p><b>signals</b> ${(o.all_signals||[]).map(s =>
      `<span class="err">${esc(s)}</span>`).join(' ') || '<i>none</i>'}</p>
    <ul>${(o.honesty_labels||[]).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>
    <button onclick="loadCommitSim()">← back</button>`;
};
"""

LOCAL_TX_SECTIONS = """
<section id="tool-local-tx-section"><h2>Finalis Transaction Twin + Proof-of-Execution</h2>
<ul class="labels"><small>
<li>FINALIS_TRANSACTION_TWIN_ONLY / LOCAL_REVERSIBLE_COMMIT_ONLY — commits only to local, reversible internal state.</li>
<li>NO_EXTERNAL_EFFECT / NO_PROVIDER_CALL / NO_MESSAGE / NO_PAYMENT / NO_NETWORK — never leaves the box.</li>
<li>B8_EVIDENCE_ONLY — the B8 envelope is evidence; B9 recomputes every factor and grants no authority.</li>
<li>PROOF_OF_EXECUTION_LOCAL_ONLY / PROOF_CARRYING_CERTIFICATE — proof of a local commit, not an external act.</li>
<li>SOURCE_SURFACE_NON_AUTHORITATIVE / CONTEXT_SLICE_NON_AUTHORITATIVE — surfaces and context confer no authority.</li>
<li>INERT_OUTBOX_NEVER_RELEASES / EFFECTOR_EXCLUSIVE_GATE — the outbox is inert; no effector is reachable.</li>
<li>NOT_PRODUCTION_READY / NOT_PRODUCTION_AUTONOMOUS_EXECUTION.</li>
</small></ul>
<div id="tool-local-tx-summary"><i>Loading Finalis Transaction Twin…</i></div>
<div id="tool-local-tx-list"></div>
</section>
"""

LOCAL_TX_JS = """
window.loadLocalTxSection = async (me) => { await loadLocalTx(); };

window.loadLocalTx = async () => {
  let reg; try { reg = await get('/ai-tools/local-transactions/registry'); }
  catch (e) { $('tool-local-tx-summary').innerHTML =
    '<i>The Finalis Transaction Twin is not available for your role.</i>'; return; }
  $('tool-local-tx-summary').innerHTML =
    `<p><b>requests</b> ${esc(String(reg.local_transaction_request_count))} ·
      <b>outcomes</b> ${esc(String(reg.local_transaction_outcome_count))}</p>` +
    '<p><small>' + Object.entries(reg.outcomes_by_status || {}).map(
      ([k, v]) => `${esc(k)}: <b>${esc(String(v))}</b>`).join(' · ') + '</small></p>';
  let reqs = []; try { reqs = await get('/ai-tools/local-transactions'); }
  catch (e) {}
  $('tool-local-tx-list').innerHTML = (reqs.length ?
    '<table><tr><th>Transaction</th><th>Target</th><th>Surface</th><th></th></tr>' +
    reqs.map(r => `<tr><td><small>${esc((r.transaction_id||'').slice(0,8))}
       </small></td><td><small>${esc(r.object_reference||'')}</small></td>
       <td><small>${esc(r.source_surface||'')}</small></td>
       <td><button onclick="openLocalTxOutcome('${esc(r.transaction_id)}')">
       Twin</button></td></tr>`).join('') + '</table>'
    : '<i>No local transactions yet.</i>');
};

window.openLocalTxOutcome = async (tid) => {
  const base = '/ai-tools/local-transactions/' + tid;
  const o = await get(base + '/outcome');
  let vr = null; try { vr = (await send('POST', base + '/verify', {})).data; }
  catch (e) {}
  const gate = o.b9_release_gate_report || {};
  const cert = o.certificate || {};
  const poe = o.poe_stream || {};
  const shadow = o.shadow_state || {};
  const path = o.path_compliance || {};
  const outbox = o.inert_outbox || {};
  const roll = o.rollback_readiness || {};
  const nee = o.no_external_effect_theorem || {};
  const surf = o.source_surface_isolation || {};
  const ctx = o.context_slice || {};
  const fw = o.contaminated_authority_firewall || {};
  $('tool-local-tx-list').innerHTML = `
    <h3>Transaction twin ${esc(tid.slice(0,8))}
      <span class="badge">${esc(o.b9_status)}</span></h3>
    <p><b>decision</b> ${esc(o.b9_decision_status)} ·
      <b>kind</b> ${esc(o.b9_outcome_kind)} ·
      <b>reason</b> <small>${esc(o.dominant_reason_code)}</small></p>
    <p><b>local commit applied</b> <b class="${o.local_commit_applied ? 'ok' : ''}">${esc(
        String(o.local_commit_applied))}</b> ·
      <b>reversible</b> <b class="ok">${esc(String(roll.rollback_ready))}</b> ·
      <b>no external effect</b> <b class="${nee.theorem_holds ? 'ok' : 'err'}">${esc(
        String(nee.theorem_holds))}</b></p>
    <p><b>B8 evidence-only</b> <b class="ok">true</b> ·
      <b>source surface authoritative</b> <b class="${surf.grants_authority ? 'err' : 'ok'}">${esc(
        String(!!surf.grants_authority))}</b> ·
      <b>context slice authoritative</b> <b class="${ctx.grants_authority ? 'err' : 'ok'}">${esc(
        String(!!ctx.grants_authority))}</b> ·
      <b>authority firewall</b> <b class="${fw.firewall_status === 'CLEAN' ? 'ok' : 'err'}">${esc(
        fw.firewall_status)}</b></p>
    <p><b>path compliance</b> <b class="${path.path_compliance_result === 'PASSED'
      ? 'ok' : 'err'}">${esc(path.path_compliance_result)}</b> ·
      <b>shadow state hash</b> <code>${esc((shadow.shadow_state_hash||'').slice(0,14))}…</code></p>
    <p><b>certificate</b> <code>${esc((cert.certificate_hash||'').slice(0,14))}…</code> ·
      <b>PoE stream</b> <code>${esc((poe.poe_stream_hash||'').slice(0,14))}…</code> ·
      <b>PoE stream</b> <b class="${poe.stream_status === 'COMPLETE' ? 'ok' : 'err'}">${esc(
        poe.stream_status)}</b></p>
    <p><b>inert outbox</b> <b class="${outbox.outbox_status === 'INERT' ? 'ok' : 'err'}">${esc(
        outbox.outbox_status)}</b> ·
      <b>rollback hash</b> <code>${esc((roll.rollback_hash||'').slice(0,14))}…</code></p>
    <p><b>release gate</b> <b class="${gate.release_gate_status === 'PASSED'
      ? 'ok' : 'err'}">${esc(gate.release_gate_status)}</b>
      · <b>decision hash</b> <code>${esc((o.b9_decision_hash||'').slice(0,14))}…</code>
      · <b>verify</b> ${vr ? `<b class="${vr.b9_decision_hash_valid ? 'ok' : 'err'}">${
        esc(vr.verification_status)}</b>` : 'n/a'}</p>
    <p><b>signals</b> ${(o.all_signals||[]).map(s =>
      `<span class="err">${esc(s)}</span>`).join(' ') || '<i>none</i>'}</p>
    <ul>${(o.honesty_labels||[]).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>
    <button onclick="loadLocalTx()">← back</button>`;
};
"""

LOCAL_RECOVERY_SECTIONS = """
<section id="tool-recovery-section"><h2>Recovery Safety Case + Chaos Sentinel + Proof-of-Recovery</h2>
<ul class="labels"><small>
<li>LOCAL_RECOVERY_ONLY / TRANSACTION_RECOVERY_TWIN_ONLY — local recovery/rollback/abort/quarantine only; no external effect.</li>
<li>PROOF_OF_RECOVERY_LOCAL_ONLY / RECOVERY_SAFETY_CASE_LOCAL_ONLY — proof/safety-case are evidence, never authority.</li>
<li>DOUBLE_ENTRY_RECONCILIATION_CHECKED / SAFETY_MONOTONICITY_CHECKED — recovery never increases authority/autonomy/scope.</li>
<li>LOCAL_ROLLBACK_ONLY / EMERGENCY_ABORT_SUPPORTED / CHAOS_SENTINEL_TESTED.</li>
<li>RECOVERY_AUTHORITY_FIREWALL_ENABLED — recovery authority is server-side only; channel/document/LLM/context rejected.</li>
<li>INERT_OUTBOX_REMAINS_INERT / SOURCE_SURFACE_ISOLATION_PRESERVED / NO_EXTERNAL_EFFECT / NO_PROVIDER_CALL.</li>
<li>NOT_PRODUCTION_READY.</li>
</small></ul>
<div id="tool-recovery-summary"><i>Loading recovery runtime…</i></div>
<div id="tool-recovery-list"></div>
</section>
"""

LOCAL_RECOVERY_JS = """
window.loadRecoverySection = async (me) => { await loadRecovery(); };

window.loadRecovery = async () => {
  let reg; try { reg = await get('/ai-tools/local-transactions/recovery/registry'); }
  catch (e) { $('tool-recovery-summary').innerHTML =
    '<i>The recovery runtime is not available for your role.</i>'; return; }
  $('tool-recovery-summary').innerHTML =
    `<p><b>recoveries</b> ${esc(String(reg.recovery_outcome_count))} ·
      <b>requests</b> ${esc(String(reg.recovery_request_count))}</p>` +
    '<p><small>' + Object.entries(reg.outcomes_by_state || {}).map(
      ([k, v]) => `${esc(k)}: <b>${esc(String(v))}</b>`).join(' · ') + '</small></p>';
  let rows = []; try { rows = await get('/ai-tools/local-transactions/recovery/list'); }
  catch (e) {}
  $('tool-recovery-list').innerHTML = (rows.length ?
    '<table><tr><th>Recovery</th><th>Transaction</th><th>Action</th><th>State</th><th></th></tr>' +
    rows.map(r => `<tr><td><small>${esc((r.recovery_id||'').slice(0,8))}</small></td>
       <td><small>${esc((r.transaction_id||'').slice(0,8))}</small></td>
       <td><small>${esc(r.desired_recovery_action||'')}</small></td>
       <td><small>${esc(r.final_recovery_state||'')}</small></td>
       <td><button onclick="openRecoveryOutcome('${esc(r.recovery_id)}')">
       Twin</button></td></tr>`).join('') + '</table>'
    : '<i>No recovery runs yet.</i>');
};

window.openRecoveryOutcome = async (rid) => {
  const base = '/ai-tools/local-transactions/recovery';
  const o = await get(base + '/outcome?recovery_id=' + encodeURIComponent(rid));
  let vr = null; try { vr = (await send('POST', base + '/verify?recovery_id=' +
    encodeURIComponent(rid), {})).data; } catch (e) {}
  const gate = o.b91_release_gate_report || {};
  const chaos = o.b91_chaos_harness || {};
  const sc = o.recovery_safety_case || {};
  const por = o.por_stream || {};
  const fw = o.recovery_authority_firewall || {};
  const rb = o.rollback_executor || {};
  const q = o.quarantine || {};
  $('tool-recovery-list').innerHTML = `
    <h3>Recovery twin ${esc(rid.slice(0,8))}
      <span class="badge">${esc(o.final_recovery_state)}</span></h3>
    <p><b>decision</b> ${esc(o.recovery_decision_status)} ·
      <b>action</b> ${esc(o.desired_recovery_action)} ·
      <b>reason</b> <small>${esc(o.dominant_reason_code)}</small></p>
    <p><b>recovery applied</b> <b class="${o.recovery_applied ? 'ok' : ''}">${esc(
        String(o.recovery_applied))}</b> ·
      <b>no external effect</b> <b class="${o.no_external_effect ? 'ok' : 'err'}">${esc(
        String(o.no_external_effect))}</b> ·
      <b>inert outbox preserved</b> <b class="${o.inert_outbox_preserved ? 'ok' : 'err'}">${esc(
        String(o.inert_outbox_preserved))}</b></p>
    <p><b>safety monotonicity</b> <b class="${o.safety_monotonicity_passed ? 'ok' : 'err'}">${esc(
        String(o.safety_monotonicity_passed))}</b> ·
      <b>double-entry reconciliation</b> <b class="${o.double_entry_reconciliation_passed ? 'ok' : 'err'}">${esc(
        String(o.double_entry_reconciliation_passed))}</b> ·
      <b>idempotency</b> <b class="${o.idempotency_preserved ? 'ok' : 'err'}">${esc(
        String(o.idempotency_preserved))}</b></p>
    <p><b>authority firewall</b> <b class="${fw.firewall_status === 'CLEAN' ? 'ok' : 'err'}">${esc(
        fw.firewall_status)}</b> · <b>rollback</b> ${esc(rb.rollback_result)} ·
      <b>quarantine</b> <b class="${q.quarantined ? 'err' : 'ok'}">${esc(
        String(!!q.quarantined))}</b> · <b>stuck</b> ${esc(String(!!o.stuck))} ·
      <b>tampered</b> ${esc(String(!!o.tampered))}</p>
    <p><b>Proof-of-Execution recovery</b> ${esc((o.poe_stream_recovery||{}).classification)} ·
      <b>PoR stream</b> <b class="${por.stream_status === 'COMPLETE' ? 'ok' : 'err'}">${esc(
        por.stream_status)}</b></p>
    <p><b>recovery twin</b> <code>${esc((o.recovery_twin_hash||'').slice(0,14))}…</code> ·
      <b>certificate</b> <code>${esc((o.recovery_certificate_hash||'').slice(0,14))}…</code> ·
      <b>safety case</b> <b class="${sc.verification_status === 'VALID' ? 'ok' : 'err'}">${esc(
        sc.verification_status)}</b></p>
    <p><b>chaos sentinel</b> <b class="${chaos.all_crashes_safe ? 'ok' : 'err'}">${esc(
        chaos.harness_status)}</b> (${esc(String(chaos.phase_count))} phases) ·
      <b>release gate</b> <b class="${gate.release_gate_status === 'PASSED' ? 'ok' : 'err'}">${esc(
        gate.release_gate_status)}</b>
      · <b>verify</b> ${vr ? `<b class="${vr.b91_decision_hash_valid ? 'ok' : 'err'}">${
        esc(vr.verification_status)}</b>` : 'n/a'}</p>
    <p><b>signals</b> ${(o.all_signals||[]).filter(s => s !== 'RECOVERY_CLEAN').map(s =>
      `<span class="err">${esc(s)}</span>`).join(' ') || '<i>none</i>'}</p>
    <ul>${(o.honesty_labels||[]).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>
    <button onclick="loadRecovery()">← back</button>`;
};
"""

WORK_OBS_SECTIONS = """
<section id="tool-work-obs-section"><h2>Governed Work Lineage Observatory</h2>
<ul class="labels"><small>
<li>LOCAL_WORK_OBSERVABILITY_ONLY / DERIVED_EVIDENCE_NOT_AUTHORITY — observes B9/B9.1; grants no authority.</li>
<li>READ_ONLY_OVER_B9_AND_B9_1 — never commits, recovers, rolls back, aborts or releases the outbox.</li>
<li>PROOF_OF_WORK_OUTCOME_IS_EVIDENCE_ONLY — the PoWO authorizes nothing.</li>
<li>NO_EXTERNAL_PROVIDER_RUNTIME / NO_EXTERNAL_EFFECT / NO_EXTERNAL_DELIVERY / INERT_OUTBOX_REMAINS_INERT.</li>
<li>NO_SECRET_STORED / NO_HIDDEN_CHAIN_OF_THOUGHT_STORED / NOT_PRODUCTION_READY.</li>
</small></ul>
<div id="tool-work-obs-summary"><i>Loading governed work lineage…</i></div>
<div id="tool-work-obs-list"></div>
</section>
"""

WORK_OBS_JS = """
window.loadWorkObsSection = async (me) => { await loadWorkObs(); };

window.loadWorkObs = async () => {
  const base = '/ai-tools/local-transactions/observability';
  let reg; try { reg = await get(base + '/registry'); }
  catch (e) { $('tool-work-obs-summary').innerHTML =
    '<i>The governed work observatory is not available for your role.</i>'; return; }
  $('tool-work-obs-summary').innerHTML =
    `<p><b>work runs</b> ${esc(String(reg.work_run_count))}</p>` +
    '<p><small>' + Object.entries(reg.outcomes_by_truth_state || {}).map(
      ([k, v]) => `${esc(k)}: <b>${esc(String(v))}</b>`).join(' · ') + '</small></p>';
  let rows = []; try { rows = await get(base + '/work-runs'); } catch (e) {}
  $('tool-work-obs-list').innerHTML = (rows.length ?
    '<table><tr><th>Work run</th><th>Trigger</th><th>State</th><th>Truth</th><th></th></tr>' +
    rows.map(r => `<tr><td><small>${esc((r.work_run_id||'').slice(0,8))}</small></td>
       <td><small>${esc(r.trigger_type||'')}</small></td>
       <td><small>${esc(r.work_run_state||'')}</small></td>
       <td><small>${esc(r.work_outcome_truth_state||'')}</small></td>
       <td><button onclick="openWorkObs('${esc(r.work_run_id)}')">Lineage</button></td></tr>`
      ).join('') + '</table>'
    : '<i>No governed work runs observed yet.</i>');
};

window.openWorkObs = async (wid) => {
  const base = '/ai-tools/local-transactions/observability';
  const o = await get(base + '/work-run/' + encodeURIComponent(wid));
  let vr = null; try { vr = (await send('POST', base + '/verify-work-run',
    {work_run_id: wid})).data; } catch (e) {}
  const powo = o.proof_of_work_outcome || {};
  const twin = o.work_observation_twin || {};
  const graph = o.causal_work_graph || {};
  const can = o.b92_canary_harness || {};
  const fw = o.gateway_boundary || {};
  const neg = o.negative_space || {};
  $('tool-work-obs-list').innerHTML = `
    <h3>Work lineage ${esc(wid.slice(0,8))}
      <span class="badge">${esc(o.work_run_state)}</span></h3>
    <p><b>truth</b> <b class="${o.work_outcome_truth_state === 'PROVEN' ? 'ok' :
      (['CONTRADICTED','TAMPERED','REVOKED'].includes(o.work_outcome_truth_state) ? 'err' : '')}">${esc(
        o.work_outcome_truth_state)}</b> ·
      <b>trigger</b> ${esc(o.trigger_type)} ·
      <b>certified</b> <b class="${o.work_outcome_certified ? 'ok' : ''}">${esc(
        String(o.work_outcome_certified))}</b></p>
    <p><b>origin</b> ${esc((o.work_origin||{}).origin_status)} ·
      <b>identity</b> ${esc((o.principal_continuity||{}).continuity_status)} ·
      <b>memory</b> ${esc((o.memory_snapshot||{}).snapshot_status)} ·
      <b>approval</b> ${esc((o.approval_continuity||{}).approval_status)}</p>
    <p><b>gateway boundary</b> <b class="${fw.gateway_decision === 'ALLOW' ? 'ok' : 'err'}">${esc(
        fw.gateway_decision)}</b> · <b>secret to model</b> <b class="${
        fw.secret_exposed_to_model ? 'err' : 'ok'}">${esc(String(!!fw.secret_exposed_to_model))}</b> ·
      <b>transaction</b> ${esc((o.transaction_binding||{}).binding_status)} ·
      <b>recovery</b> ${esc((o.recovery_binding||{}).binding_status)}</p>
    <p><b>artifact lineage</b> ${esc((o.artifact_lineage||{}).lineage_status)} ·
      <b>delivery</b> ${esc((o.delivery_intent||{}).delivery_status)} ·
      <b>revocation</b> ${esc((o.revocation||{}).revocation_status)} ·
      <b>missing critical</b> <b class="${neg.no_critical_missing ? 'ok' : 'err'}">${esc(
        String(!neg.no_critical_missing))}</b></p>
    <p><b>no external effect</b> <b class="${o.no_external_effect ? 'ok' : 'err'}">${esc(
        String(o.no_external_effect))}</b> · <b>observer</b> ${esc(o.observer_health_state)} ·
      <b>canaries safe</b> <b class="${can.all_canaries_safe ? 'ok' : 'err'}">${esc(
        String(can.all_canaries_safe))}</b> (${esc(String(can.canary_count))})</p>
    <p><b>PoWO</b> <b class="${powo.verification_status === 'VALID' ? 'ok' : 'err'}">${esc(
        powo.verification_status)}</b>
      · <b>causal graph</b> ${esc(String(graph.node_count))} nodes / ${esc(String(graph.edge_count))} edges
      · <b>twin</b> <code>${esc((o.work_observation_twin_hash||'').slice(0,14))}…</code>
      · <b>verify</b> ${vr ? `<b class="${vr.b92_decision_hash_valid ? 'ok' : 'err'}">${
        esc(vr.verification_status)}</b>` : 'n/a'}</p>
    <p><small>${esc(o.powo_warning || '')}</small></p>
    <p><b>signals</b> ${(o.all_signals||[]).map(s =>
      `<span class="err">${esc(s)}</span>`).join(' ') || '<i>none</i>'}</p>
    <ul>${(o.honesty_labels||[]).map(l =>
      `<li><small>${esc(l)}</small></li>`).join('')}</ul>
    <button onclick="loadWorkObs()">← back</button>`;
};
"""

WORK_INBOX_SECTIONS = """
<section id="tool-work-inbox-section"><h2>Employee Work Inbox — R-FSAFEQ Admission</h2>
<ul class="labels"><small>
<li>INBOX_AND_ADMISSION_ONLY / ORDER_RECOMMENDATION_ONLY — governed intake + admission; never executes work.</li>
<li>NO_EMP_A2_RUN_CREATED / NO_EXECUTION_STARTED / NO_PROVIDER_CALLED / NO_EXTERNAL_EFFECT.</li>
<li>CALIBRATION_DISABLED_OR_NOT_EXECUTION_VALIDATED — conformal estimation is schema-only and disabled.</li>
<li>ESTIMATED_DEMAND_NOT_ACTUAL_USAGE / VIRTUAL_BACKLOG_IS_ADMISSION_SIDE_PROXY.</li>
<li>DEADLINE_NOT_GUARANTEED / NOT_PRODUCTION_READY.</li>
</small></ul>
<div id="tool-work-inbox-summary"><i>Loading Employee Work Inbox…</i></div>
<div id="tool-work-inbox-list"></div>
</section>
"""

WORK_INBOX_JS = """
window.loadWorkInboxSection = async (me) => { await loadWorkInbox(); };

window.loadWorkInbox = async () => {
  const base = '/ai-employee/work-inbox';
  let counts; try { counts = await get(base + '/counts'); }
  catch (e) { $('tool-work-inbox-summary').innerHTML =
    '<i>The Employee Work Inbox is not available for your role.</i>'; return; }
  $('tool-work-inbox-summary').innerHTML =
    '<p><small>' + Object.entries(counts.counts_by_state || {}).map(
      ([k, v]) => `${esc(k)}: <b>${esc(String(v))}</b>`).join(' · ') +
    (Object.keys(counts.counts_by_state||{}).length ? '' : '<i>No work items yet.</i>') + '</small></p>';
  let rows = []; try { rows = await get(base + '/items?limit=50'); } catch (e) {}
  $('tool-work-inbox-list').innerHTML = (rows.length ?
    '<table><tr><th>Work item</th><th>Type</th><th>State</th><th>Priority</th><th>Shard</th><th></th></tr>' +
    rows.map(r => `<tr><td><small>${esc((r.work_item_id||'').slice(0,10))}</small></td>
       <td><small>${esc(r.work_type||'')}</small></td>
       <td><small>${esc(r.work_item_state||'')}</small></td>
       <td><small>${esc(r.priority_class||'')}</small></td>
       <td><small>${esc(String(r.queue_shard))}</small></td>
       <td><button onclick="openWorkItem('${esc(r.work_item_id)}')">Detail</button></td></tr>`
      ).join('') + '</table>'
    : '<i>No work items yet.</i>');
};

window.openWorkItem = async (wid) => {
  const base = '/ai-employee/work-inbox/items/' + wid;
  const it = await get(base);
  let adm = {}; try { adm = await get(base + '/admission'); } catch (e) {}
  let hp = {}; try { hp = (await get(base + '/handoff-preview')).handoff_ready || {}; } catch (e) {}
  const dem = it.work_demand_envelope || {};
  $('tool-work-inbox-list').innerHTML = `
    <h3>Work item ${esc(wid.slice(0,10))}
      <span class="badge">${esc(it.work_item_state)}</span></h3>
    <p><b>type</b> ${esc(it.work_type)} · <b>disposition</b> ${esc(it.disposition)} ·
      <b>priority</b> ${esc(it.priority_class)} · <b>queue shard</b> ${esc(String(it.queue_shard))}</p>
    <p><b>missing fields</b> ${(it.missing_input_fields||[]).map(esc).join(', ') || '<i>none</i>'} ·
      <b>approval</b> ${esc(it.approval_requirement)} ·
      <b>capabilities</b> ${(it.required_capabilities||[]).map(esc).join(', ')}</p>
    <p><b>demand floor</b> <code>${esc(JSON.stringify(dem.deterministic_floor||{}))}</code></p>
    <p><b>safety upper</b> <code>${esc(JSON.stringify(dem.safety_upper||{}))}</code> ·
      <b>demand valid</b> <b class="${it.demand_envelope_valid ? 'ok' : 'err'}">${esc(String(it.demand_envelope_valid))}</b></p>
    <p><b>calibration</b> ${esc(it.calibration_status)} · <b>drift</b> ${esc(it.drift_status)} ·
      <b>risk budget</b> ${esc(it.risk_budget_status)} · <b>backlog</b> ${esc(it.virtual_backlog_status)}</p>
    <p><b>admission memory</b> ${esc(it.admission_memory_state)} ·
      <b>fairness deficit</b> ${esc(String(it.fairness_deficit))} (${esc(it.fairness_deficit_class)})</p>
    <p><b>claim</b> ${esc(String(it.active_fencing_token||0))} · <b>assignee</b> ${esc(it.assignee_type)} ·
      <b>receipt</b> <code>${esc((it.admission_receipt_hash||'').slice(0,14))}…</code></p>
    <p><b>handoff ready</b> <b class="${hp.handoff_ready ? 'ok' : ''}">${esc(String(!!hp.handoff_ready))}</b> ·
      <b>decision hash</b> <code>${esc((it.decision_hash||'').slice(0,14))}…</code></p>
    <p><b>reason codes</b> ${(it.reason_codes||[]).map(s => `<span class="badge">${esc(s)}</span>`).join(' ')}</p>
    <ul>${(it.honesty_labels||[]).map(l => `<li><small>${esc(l)}</small></li>`).join('')}</ul>
    <button onclick="loadWorkInbox()">← back</button>`;
};
"""

PORTAL_PAGE = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Finalis — Case Command Center</title><style>{STYLE}</style></head><body>
<h1>Case Command Center</h1>
<p>What should I do today to close more cases and lose fewer clients?
 <button id="logout">Log out</button></p>
<p id="loading">Loading dashboard…</p>
<p id="error" class="err" hidden>Failed to load. <button onclick="boot()">Retry</button></p>
<div id="app" hidden>
<section id="summary"><h2>Today</h2><div class="cards" id="summary-cards"></div></section>
<section><h2>Today’s Action Queue</h2><div id="action-queue"></div></section>
<section><h2>Waiting for Your Approval</h2><div id="approvals"></div></section>
<section><h2>Cases</h2><div id="cases"></div></section>
<section><h2>Case Detail</h2><div id="case-detail"><i>Select a case.</i></div></section>
<section><h2>Pipeline</h2><div id="pipeline"></div></section>
<section><h2>Recent Activity</h2><ul id="activity"></ul></section>
{WIRING_SECTIONS}
{QUOTES_SECTIONS}
{EVIDENCE_SECTIONS}
{CRM_SECTIONS}
{WORKBENCH_SECTIONS}
{AIEMP_SECTIONS}
{TASKS_SECTIONS}
{RUNS_SECTIONS}
{APPROVALS_SECTIONS}
{LIFECYCLE_SECTIONS}
{ARTIFACTS_SECTIONS}
{TOOLS_SECTIONS}
{QUALITY_SECTIONS}
{CONTRACTS_SECTIONS}
{ACTIONS_SECTIONS}
{BROKER_SECTIONS}
{RUNTIME_SECTIONS}
{WRITE_INTENT_SECTIONS}
{COMMIT_SIM_SECTIONS}
{LOCAL_TX_SECTIONS}
{LOCAL_RECOVERY_SECTIONS}
{WORK_OBS_SECTIONS}
{WORK_INBOX_SECTIONS}
</div>
<script>
const T = () => localStorage.getItem('finalis_token');
const H = () => ({{'Authorization':'Bearer '+T(),'Content-Type':'application/json'}});
const get = async (p) => {{ const r = await fetch(p, {{headers: H()}});
  if (r.status===401) location.href='/'; if(!r.ok) throw new Error(p); return r.json(); }};
const post = async (p, body) => {{ const r = await fetch(p, {{method:'POST',
  headers:H(), body: JSON.stringify(body||{{}})}}); return r.json(); }};
document.getElementById('logout').onclick = () => {{
  localStorage.removeItem('finalis_token'); location.href='/'; }};

async function boot() {{
  document.getElementById('error').hidden = true;
  try {{
    const [s, aq, ap, cases, pipe, act] = await Promise.all([
      get('/dashboard/summary'), get('/dashboard/action-queue'),
      get('/dashboard/approval-queue'), get('/cases'),
      get('/dashboard/pipeline'), get('/dashboard/activity')]);
    document.getElementById('summary-cards').innerHTML = [
      ['active cases', s.active_cases_count],['need attention', s.attention_required_count],
      ['pending approvals', s.pending_approvals_count],['stuck', s.stuck_cases_count],
      ['pipeline €', Math.round(s.pipeline_value)],['won €', Math.round(s.won_value_period)]]
      .map(([k,v])=>`<div class="card"><b>${{v}}</b><span>${{k}}</span></div>`).join('');
    document.getElementById('action-queue').innerHTML = aq.length ? aq.slice(0,8)
      .map(a=>`<div class="card"><b>${{a.title}}</b><br>${{a.reason}}<br>
        <i>${{a.recommended_action}}</i></div>`).join('') : '<i>Nothing urgent.</i>';
    document.getElementById('approvals').innerHTML = ap.length ? ap.map(a=>
      `<div class="card" data-approval="${{a.id}}"><span class="badge">${{a.risk_level}}</span>
       ${{a.reason}}<blockquote>${{a.draft_message}}</blockquote>
       <button onclick="decide('${{a.id}}','approve')">Approve</button>
       <button onclick="decide('${{a.id}}','reject')">Reject</button></div>`).join('')
      : '<i>No approvals pending.</i>';
    document.getElementById('cases').innerHTML = '<table><tr><th>Title</th><th>Client</th>'+
      '<th>State</th><th>Value</th><th></th></tr>'+cases.map(c=>
      `<tr><td>${{c.title}}</td><td>${{c.client_name||'?'}}</td><td>${{c.state}}</td>
       <td>€${{c.value_estimate}}</td><td><button onclick="openCase('${{c.id}}')">Open</button>
       </td></tr>`).join('')+'</table>';
    document.getElementById('pipeline').innerHTML = '<table><tr><th>State</th><th>Count</th>'+
      '<th>Value</th></tr>'+Object.entries(pipe).map(([st,b])=>
      `<tr><td>${{st}}</td><td>${{b.count}}</td><td>€${{b.value}}</td></tr>`).join('')+'</table>';
    document.getElementById('activity').innerHTML = act.map(e=>
      `<li>[${{e.actor_type}}] ${{e.summary}}</li>`).join('');
    document.getElementById('loading').hidden = true;
    document.getElementById('app').hidden = false;
    if (window.loadSections) loadSections();
  }} catch (e) {{
    document.getElementById('loading').hidden = true;
    document.getElementById('error').hidden = false;
  }}
}}
window.decide = async (id, decision) => {{
  await post(`/actions/${{id}}/${{decision}}`, {{}}); boot();
}};
window.openCase = async (id) => {{
  const c = await get(`/cases/${{id}}`);
  const tl = await get(`/cases/${{id}}/timeline`);
  const verify = await get(`/audit/verify/${{id}}`);
  document.getElementById('case-detail').innerHTML =
    `<h3 id="case-title">${{c.title}} — ${{c.client_name||'?'}}</h3>
     <p>State: <b id="case-state">${{c.state}}</b> · Value €${{c.value_estimate}}
     · Audit chain: <span class="${{verify.chain_valid?'ok':'err'}}">
     ${{verify.chain_valid?'VALID':'BROKEN'}}</span></p>
     <p><b>Missing:</b> ${{c.missing_items.filter(m=>m.status!=='received')
        .map(m=>m.field_key).join(', ')||'none'}}</p>
     <p><b>Promises:</b> ${{c.promises.map(p=>p.promisor+': '+p.what+' ('+p.status+')')
        .join('; ')||'none'}}</p>
     <p><b>Documents:</b> ${{c.documents.map(d=>d.filename).join(', ')||'none'}}</p>
     <p><b>Offers:</b> ${{c.offers.map(o=>o.status+' €'+o.price).join('; ')||'none'}}</p>
     <p>
     <button onclick="runLoop('${{id}}')">Run completion loop</button>
     <button onclick="requestPhoto('${{id}}')">Request photos</button>
     <select id="state-select">
       ${{['DOCUMENT_ANALYSIS','QUOTE_PREPARATION','OFFER_SENT',
           'FOLLOW_UP_ACTIVE','NEGOTIATION','SCHEDULED','QUALIFIED',
           'WAITING_FOR_CLIENT_INFO','WAITING_FOR_DOCUMENTS',
           'HUMAN_REVIEW_REQUIRED','LOST','RECOVERY_LATER']
          .map(s=>`<option>${{s}}</option>`).join('')}}
     </select>
     <button onclick="doTransition('${{id}}')">Transition</button>
     <button onclick="markWon('${{id}}')">Close WON</button>
     <button onclick="scheduleFor('${{id}}')">Schedule appointment…</button>
     <button onclick="quotesFor('${{id}}')">Quotes…</button>
     <button onclick="evidenceFor('${{id}}')">Evidence…</button>
     <button onclick="proofFor('${{id}}')">Proof…</button>
     <button onclick="crmFor('${{id}}')">Customer…</button></p>
     <div id="case-msg"></div>
     <h4>Timeline (${{tl.length}})</h4>
     <ul id="case-timeline">${{tl.slice(-12).map(e=>`<li>${{e.event_type}}
       <small>${{e.actor}}</small></li>`).join('')}}</ul>`;
}};
window.runLoop = async (id) => {{
  const r = await post(`/completion-loop/run-case/${{id}}`);
  document.getElementById('case-msg').innerText =
    'Next action: '+(r.selected_action||'-')+' (gate: '+(r.gate||'-')+')';
}};
window.requestPhoto = async (id) => {{
  const r = await post('/actions/request', {{case_id:id,
    action_type:'send_photo_request', reason:'ui'}});
  document.getElementById('case-msg').innerHTML = r.upload_url ?
    `Upload link sent (mock): <a id="upload-url" href="${{r.upload_url
      .replace('https://upload.finalis.example/u/','/u/')}}">
      ${{r.upload_url}}</a>` : 'Status: '+r.status+' ('+r.reason+')';
}};
window.doTransition = async (id) => {{
  const to = document.getElementById('state-select').value;
  const r = await post(`/cases/${{id}}/transition`, {{to_state: to,
    reason: 'ui transition'}});
  document.getElementById('case-msg').innerText = r.state ?
    'Case state: '+r.state : 'Blocked: '+(r.detail||JSON.stringify(r));
  if (r.state) openCase(id);
}};
window.markWon = async (id) => {{
  const r = await post(`/cases/${{id}}/transition`, {{to_state:'WON',
    reason:'client accepted (ui)'}});
  document.getElementById('case-msg').innerText = r.state ?
    'Case state: '+r.state : 'Error: '+JSON.stringify(r);
  boot(); openCase(id);
}};
boot();
</script>
<script>{WIRING_JS}</script>
<script>{QUOTES_JS}</script>
<script>{EVIDENCE_JS}</script>
<script>{CRM_JS}</script>
<script>{WORKBENCH_JS}</script>
<script>{AIEMP_JS}</script>
<script>{TASKS_JS}</script>
<script>{RUNS_JS}</script>
<script>{APPROVALS_JS}</script>
<script>{LIFECYCLE_JS}</script>
<script>{ARTIFACTS_JS}</script>
<script>{TOOLS_JS}</script>
<script>{QUALITY_JS}</script>
<script>{CONTRACTS_JS}</script>
<script>{ACTIONS_JS}</script>
<script>{BROKER_JS}</script>
<script>{RUNTIME_JS}</script>
<script>{WRITE_INTENT_JS}</script>
<script>{COMMIT_SIM_JS}</script>
<script>{LOCAL_TX_JS}</script>
<script>{LOCAL_RECOVERY_JS}</script>
<script>{WORK_OBS_JS}</script>
<script>{WORK_INBOX_JS}</script></body></html>"""


def upload_page(token: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Finalis — Secure upload</title><style>{STYLE}</style></head><body>
<h1>Send your photos</h1>
<p id="status">Checking link…</p>
<div id="form" hidden>
  <input id="filename" value="boiler-nameplate.jpg"/>
  <button id="upload-btn">Upload photo (simulated)</button>
</div>
<p id="done" class="ok" hidden>Thank you! Your photo was received.</p>
<script>
const token = {token!r};
(async () => {{
  const r = await fetch('/upload-links/'+token);
  if (!r.ok) {{ document.getElementById('status').innerText =
    'This link is invalid or has expired.'; return; }}
  const info = await r.json();
  document.getElementById('status').innerText =
    'Requested: '+info.purpose.replaceAll('_',' ');
  document.getElementById('form').hidden = false;
}})();
document.getElementById('upload-btn').onclick = async () => {{
  const r = await fetch('/upload-links/'+token+'/upload', {{method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{filename: document.getElementById('filename').value,
                          mime:'image/jpeg', size_mb: 2.4}})}});
  if (r.ok) {{ document.getElementById('form').hidden = true;
    document.getElementById('done').hidden = false; }}
}};
</script></body></html>"""


def mount(app: FastAPI) -> None:
    @app.get("/", response_class=HTMLResponse)
    async def login_page() -> str:
        return LOGIN_PAGE

    @app.get("/portal", response_class=HTMLResponse)
    async def portal_page() -> str:
        return PORTAL_PAGE

    @app.get("/u/{token}", response_class=HTMLResponse)
    async def client_upload_page(token: str) -> str:
        return upload_page(token)
