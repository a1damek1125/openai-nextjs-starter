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
<script>{CRM_JS}</script></body></html>"""


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
