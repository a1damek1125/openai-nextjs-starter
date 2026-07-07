"""Server-rendered HTML view of the Command Center (MVP UI).

One dependency-free renderer producing a self-contained HTML page with all
11 required components. The production UI (Next.js) consumes the same
DashboardService contracts; this renderer proves the view layer end-to-end
today and doubles as the print/email digest.
"""
from __future__ import annotations

from datetime import datetime
from html import escape

from .dashboard import DashboardService

COMPONENTS = ["SummaryCards", "TodayActionQueue", "ApprovalQueue",
              "StuckCasesTable", "MissingInfoQueue", "PromiseTracker",
              "OfferFollowUpBoard", "PipelineByState", "RiskAlerts",
              "ActivityTimeline", "CaseQuickView"]

_BADGE = {"high": "#c0392b", "medium": "#e67e22", "low": "#27ae60"}


def _badge(level: str) -> str:
    color = _BADGE.get(level, "#7f8c8d")
    return (f'<span class="badge" style="background:{color}">'
            f'{escape(level)}</span>')


def render_dashboard(svc: DashboardService, *, tenant_id: str,
                     now: datetime) -> str:
    s = svc.summary(tenant_id, now=now)
    actions = svc.action_queue(tenant_id, now=now)
    approvals = svc.approval_queue(tenant_id)
    stuck = svc.stuck_cases(tenant_id, now=now)
    missing = svc.missing_info(tenant_id)
    promises = svc.promises(tenant_id, now=now)
    offers = svc.offers_followup(tenant_id, now=now)
    pipeline = svc.pipeline(tenant_id)
    risks = svc.risk_alerts(tenant_id, now=now)
    activity = svc.activity(tenant_id)

    def empty(msg: str) -> str:
        return f'<p class="empty">{escape(msg)}</p>'

    parts = [
        "<!-- component:SummaryCards -->",
        '<section id="summary"><h2>Today</h2><div class="cards">',
        *(f'<div class="card"><b>{v}</b><span>{escape(k)}</span></div>'
          for k, v in [
              ("active cases", s.active_cases_count),
              ("need attention", s.attention_required_count),
              ("pending approvals", s.pending_approvals_count),
              ("stuck", s.stuck_cases_count),
              ("overdue promises", s.overdue_promises_count),
              ("pipeline", f"€{s.pipeline_value:,.0f}"),
              ("expected close", f"€{s.expected_close_value:,.0f}"),
              ("won", f"€{s.won_value_period:,.0f}"),
          ]),
        "</div></section>",

        "<!-- component:TodayActionQueue -->",
        '<section id="action-queue"><h2>Today’s Action Queue</h2>',
        (empty("Nothing urgent — all cases progressing.") if not actions else
         "".join(
             f'<div class="action"><b>{escape(a.title)}</b> '
             f'{_badge(a.risk_level)}<br>{escape(a.reason)}<br>'
             f'<i>Recommended: {escape(a.recommended_action)}</i> '
             f'<button data-case="{a.case_id}">Do it</button></div>'
             for a in actions[:10])),
        "</section>",

        "<!-- component:ApprovalQueue -->",
        '<section id="approvals"><h2>Waiting for Your Approval</h2>',
        (empty("No approvals pending.") if not approvals else "".join(
            f'<div class="approval">{_badge(a.risk_level)} '
            f'<b>{escape(a.action_type)}</b> — {escape(a.reason)}'
            f'<blockquote>{escape(a.draft_message)}</blockquote>'
            f'<button data-approve="{a.id}">Approve</button>'
            f'<button data-edit="{a.id}">Edit</button>'
            f'<button data-reject="{a.id}">Reject</button></div>'
            for a in approvals)),
        "</section>",

        "<!-- component:StuckCasesTable -->",
        '<section id="stuck"><h2>Stuck Cases</h2>',
        (empty("No stuck cases.") if not stuck else
         "<table><tr><th>State</th><th>Days</th><th>Blocker</th>"
         "<th>Next step</th></tr>" + "".join(
             f"<tr><td>{escape(r['state'])}</td>"
             f"<td>{r['days_since_progress']}</td>"
             f"<td>{escape(r['blocker'])}</td>"
             f"<td>{escape(r['next_action'])}</td></tr>"
             for r in stuck) + "</table>"),
        "</section>",

        "<!-- component:MissingInfoQueue -->",
        '<section id="missing"><h2>Missing Information</h2>',
        (empty("Nothing missing.") if not missing else "".join(
            f"<div>{escape(row['client'])}: " + ", ".join(
                escape(i['type']) + (" (blocks quote)" if i['blocks_quote']
                                     else "")
                for i in row["items"]) + "</div>"
            for row in missing)),
        "</section>",

        "<!-- component:PromiseTracker -->",
        '<section id="promises"><h2>Promises & Deadlines</h2>',
        "".join(f"<h3>{escape(k.replace('_', ' '))} "
                f"({len(v)})</h3>" + ("".join(
                    f"<div>{escape(p['who'])}: {escape(p['what'])}</div>"
                    for p in v) or empty("—"))
                for k, v in promises.items()),
        "</section>",

        "<!-- component:OfferFollowUpBoard -->",
        '<section id="offers"><h2>Offers Waiting for Response</h2>',
        (empty("No offers waiting.") if not offers else "".join(
            f'<div class="offer">{escape(o["client"])} — '
            f'€{o["value"]:,.0f}, {o["days_without_response"]} days silent '
            f'{_badge(o["losing_risk"])}<br>'
            f'<i>{escape(o["recommendation"])}</i></div>'
            for o in offers)),
        "</section>",

        "<!-- component:PipelineByState -->",
        '<section id="pipeline"><h2>Pipeline</h2><table>'
        "<tr><th>State</th><th>Cases</th><th>Value</th></tr>",
        "".join(f"<tr><td>{escape(state)}</td><td>{b['count']}</td>"
                f"<td>€{b['value']:,.0f}</td></tr>"
                for state, b in sorted(pipeline.items())),
        "</table></section>",

        "<!-- component:RiskAlerts -->",
        '<section id="risks"><h2>Risk Alerts</h2>',
        (empty("No risk alerts.") if not risks else "".join(
            f'<div class="risk">{_badge("high")} '
            f'{escape(r["type"])}: {escape(r["detail"])}</div>'
            for r in risks)),
        "</section>",

        "<!-- component:ActivityTimeline -->",
        '<section id="activity"><h2>Recent Activity</h2>',
        (empty("No recent activity.") if not activity else "<ul>" + "".join(
            f"<li>[{escape(e.actor_type)}] {escape(e.summary)}</li>"
            for e in activity) + "</ul>"),
        "</section>",

        "<!-- component:CaseQuickView -->",
        '<section id="quickview" hidden><h2>Case Quick View</h2>'
        '<div id="quickview-body">Select a case to see its timeline, '
        'missing items, promises and evidence.</div></section>',
    ]

    body = "\n".join(parts)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Finalis — Case Command Center</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;max-width:70rem}}
.cards{{display:flex;flex-wrap:wrap;gap:.6rem}}
.card{{border:1px solid #ddd;border-radius:8px;padding:.7rem 1rem;
min-width:8rem}} .card b{{display:block;font-size:1.4rem}}
.badge{{color:#fff;border-radius:4px;padding:0 .4rem;font-size:.8rem}}
.action,.approval,.offer,.risk{{border:1px solid #eee;border-radius:8px;
padding:.6rem;margin:.4rem 0}}
table{{border-collapse:collapse}} td,th{{border:1px solid #ddd;
padding:.3rem .6rem;text-align:left}}
.empty{{color:#7f8c8d;font-style:italic}}
button{{margin-right:.3rem}}
</style></head><body>
<h1>Case Command Center</h1>
<p>What should I do today to close more cases and lose fewer clients?</p>
{body}
</body></html>"""
