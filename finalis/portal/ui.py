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
simulated. Appointments are in-memory and <b>do not survive a server
restart</b> yet. Real Google / Microsoft / Cal.com / LiveKit providers are
<b>not connected</b> (BLOCKED_BY_CREDENTIALS — adapters ready,
credentials pending).</small></p>
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
    '<i>No appointments yet (in-memory only — cleared on restart).</i>';
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
  $('quote-calc').innerHTML = `
    <p id="calc-totals">Calculated: subtotal ${data.subtotal} ·
      tax ${data.tax_total} (mock) · <b>total ${data.total}</b></p>
    <ul id="calc-gates">${gates}</ul>
    <p id="calc-scores">Price confidence: ${data.scores.price_confidence}
      · Evidence coverage: ${data.scores.evidence_coverage}
      <small>(risk &amp; clarity scores need case-context wiring —
      SCAFFOLDED_ONLY in the portal)</small></p>`;
  openQuote(id);
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
     <button onclick="quotesFor('${{id}}')">Quotes…</button></p>
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
<script>{QUOTES_JS}</script></body></html>"""


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
