"""Finalis Quote Builder / Pricing / Offer Engine — core domain logic.

Local-first CPQ brain: deterministic Decimal money math, a 15-state quote
machine with immutability after SENT/ACCEPTED, margin/discount/readiness/
feasibility safety gates, explainable risk/confidence/evidence/clarity
scores, payment schedules, versioning, and change orders. Reference
patterns (not copied): ERPNext Quotation & Pricing Rules, Odoo pricelists,
Stripe Quotes/Invoicing. Hard blockers always override scores; AI cannot
approve its own quote; an accepted quote never completes a case by itself.
"""
