"""Quote output providers — ALL MOCKS. Real PDF (Gotenberg/pdfme),
e-signature (DocuSeal/Documenso), and invoicing (Stripe/local ERP) replace
these behind the same interfaces once credentials/deployment exist."""
from __future__ import annotations

from .models import PaymentRequirement, Quote


class MockPdfProvider:
    """Renders a deterministic HTML 'document' — a placeholder for a real
    PDF renderer. No file I/O; the portal stores the HTML row."""
    name = "mock-pdf"
    is_mock = True

    def render(self, quote: Quote) -> str:
        lines = "".join(
            f"<tr><td>{li.description}</td><td>{li.quantity}</td>"
            f"<td>{li.price_after_discount} {quote.currency}</td>"
            f"<td>{li.line_total} {quote.currency}</td></tr>"
            for li in quote.line_items)
        assumptions = "".join(f"<li>{a}</li>" for a in quote.assumptions)
        exclusions = "".join(f"<li>{e}</li>" for e in quote.exclusions)
        return (f"<html><body><h1>Quote v{quote.version}</h1>"
                f"<p>State: {quote.state} · MOCK DOCUMENT — not a real "
                f"PDF</p><table><tr><th>Item</th><th>Qty</th><th>Unit</th>"
                f"<th>Total</th></tr>{lines}</table>"
                f"<p>Subtotal: {quote.subtotal} {quote.currency} · "
                f"Tax: {quote.tax_total} · Total: <b>{quote.total} "
                f"{quote.currency}</b></p>"
                f"<h3>Assumptions</h3><ul>{assumptions}</ul>"
                f"<h3>Exclusions</h3><ul>{exclusions}</ul>"
                f"</body></html>")


class MockSignatureProvider:
    """SCAFFOLDED_ONLY — interface reserved for DocuSeal/Documenso."""
    name = "mock-signature"
    is_mock = True
    status = "SCAFFOLDED_ONLY"

    def request_signature(self, quote: Quote) -> None:
        raise NotImplementedError(
            "e-signature provider is scaffolded only — acceptance today "
            "uses AcceptanceEvidence (call segment, e-mail, portal click)")


class MockInvoiceHandoffProvider:
    """Emits the handoff payload a real invoicing engine would consume.
    Nothing is invoiced — this records WHAT would be invoiced."""
    name = "mock-invoice-handoff"
    is_mock = True

    def handoff(self, quote: Quote,
                requirements: list[PaymentRequirement]) -> dict:
        return {"provider": self.name, "is_mock": True,
                "quote_id": quote.id, "case_id": quote.case_id,
                "currency": quote.currency, "total": str(quote.total),
                "requirements": [
                    {"label": r.label, "amount": str(r.amount),
                     "trigger": r.trigger,
                     "blocks_fulfillment": r.blocks_fulfillment_until_paid}
                    for r in requirements]}
