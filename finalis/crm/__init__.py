"""Finalis Relationship Core — own-IP, case-first CRM foundation (CRM-A).

Not a legacy CRM clone: the relationship graph exists to answer who the
customer is, what both sides promised, what consent allows, and which
facts are verified — so cases close correctly. External CRMs (HubSpot,
Salesforce, Pipedrive, Zoho, Odoo, Suite/Espo/Twenty) are OPTIONAL,
replaceable adapters behind contracts; Finalis stays the source of
operational truth for case work. Consent is non-overrideable, AI-suggested
memory needs human verification, merges need explicit decisions, and no
graph edge ever crosses a tenant boundary.
"""
