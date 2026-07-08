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
     <button onclick="markWon('${{id}}')">Close WON</button></p>
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
</script></body></html>"""


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
