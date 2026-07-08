"""LifecycleVector — formal multi-dimensional case state + derived outcomes."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LeadState(str, Enum):
    NEW = "NEW"
    QUALIFYING = "QUALIFYING"
    QUALIFIED = "QUALIFIED"
    DISQUALIFIED = "DISQUALIFIED"


class DealState(str, Enum):
    NO_DEAL = "NO_DEAL"
    QUOTING = "QUOTING"
    OFFER_DRAFTED = "OFFER_DRAFTED"
    OFFER_APPROVAL_REQUIRED = "OFFER_APPROVAL_REQUIRED"
    OFFER_SENT = "OFFER_SENT"
    NEGOTIATION = "NEGOTIATION"
    ACCEPTED_BY_CLIENT = "ACCEPTED_BY_CLIENT"
    WON = "WON"
    DECLINED_BY_CLIENT = "DECLINED_BY_CLIENT"
    EXPIRED = "EXPIRED"
    LOST = "LOST"


class TransactionState(str, Enum):
    NO_INVOICE_REQUIRED = "NO_INVOICE_REQUIRED"
    INVOICE_REQUIRED = "INVOICE_REQUIRED"
    INVOICE_DRAFTED = "INVOICE_DRAFTED"
    INVOICE_ISSUED = "INVOICE_ISSUED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_OVERDUE = "PAYMENT_OVERDUE"
    REFUND_REQUESTED = "REFUND_REQUESTED"
    REFUNDED = "REFUNDED"
    WAIVED_BY_HUMAN = "WAIVED_BY_HUMAN"


class FulfillmentState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED = "REQUIRED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_SUPPLIER = "WAITING_FOR_SUPPLIER"
    WAITING_FOR_TECHNICIAN = "WAITING_FOR_TECHNICIAN"
    WAITING_FOR_CUSTOMER = "WAITING_FOR_CUSTOMER"
    BLOCKED = "BLOCKED"
    DELIVERED = "DELIVERED"
    SERVICE_COMPLETED = "SERVICE_COMPLETED"
    COMPLETION_CONFIRMATION_REQUIRED = "COMPLETION_CONFIRMATION_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CustomerState(str, Enum):
    PROSPECT = "PROSPECT"
    ACTIVE_LEAD = "ACTIVE_LEAD"
    FIRST_TIME_CUSTOMER = "FIRST_TIME_CUSTOMER"
    ACTIVE_CUSTOMER = "ACTIVE_CUSTOMER"
    REPEAT_CUSTOMER = "REPEAT_CUSTOMER"
    VIP_CUSTOMER = "VIP_CUSTOMER"
    AT_RISK = "AT_RISK"
    INACTIVE = "INACTIVE"
    LOST_CUSTOMER = "LOST_CUSTOMER"
    WIN_BACK_TARGET = "WIN_BACK_TARGET"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"


class SupportState(str, Enum):
    NONE = "NONE"
    COMPLAINT_OPEN = "COMPLAINT_OPEN"
    COMPLAINT_RESOLVED = "COMPLAINT_RESOLVED"
    WARRANTY_ACTIVE = "WARRANTY_ACTIVE"
    SUPPORT_ACTIVE = "SUPPORT_ACTIVE"


class PostSaleState(str, Enum):
    NONE = "NONE"
    CHECKIN_SCHEDULED = "CHECKIN_SCHEDULED"
    REVIEW_REQUESTED = "REVIEW_REQUESTED"
    UPSELL_ELIGIBLE = "UPSELL_ELIGIBLE"
    CROSS_SELL_ELIGIBLE = "CROSS_SELL_ELIGIBLE"
    RENEWAL_PENDING = "RENEWAL_PENDING"
    NURTURE_SEQUENCE = "NURTURE_SEQUENCE"
    WIN_BACK_LATER = "WIN_BACK_LATER"


PAID_STATES = {TransactionState.PAID, TransactionState.WAIVED_BY_HUMAN,
               TransactionState.NO_INVOICE_REQUIRED}
FULFILLED_STATES = {FulfillmentState.COMPLETED, FulfillmentState.DELIVERED,
                    FulfillmentState.SERVICE_COMPLETED,
                    FulfillmentState.NOT_REQUIRED}
DEAL_POSITIVE = {DealState.ACCEPTED_BY_CLIENT, DealState.WON}


@dataclass
class LifecycleVector:
    """The 7-dimension state of one case + its customer context."""
    lead: LeadState = LeadState.NEW
    deal: DealState = DealState.NO_DEAL
    transaction: TransactionState = TransactionState.NO_INVOICE_REQUIRED
    fulfillment: FulfillmentState = FulfillmentState.NOT_REQUIRED
    customer: CustomerState = CustomerState.PROSPECT
    support: SupportState = SupportState.NONE
    post_sale: PostSaleState = PostSaleState.NONE
    # Flags feeding hard blockers / invariants.
    opted_out: bool = False
    consent_valid: bool = True

    # -- derived outcome views (computed, never stored) ------------------------
    def derived_outcome_view(self) -> Optional[str]:
        """The business-truth view: a deal can be WON while the case is not
        truly finished. Returns None while no view applies."""
        if self.deal in DEAL_POSITIVE:
            paid = self.transaction in PAID_STATES
            fulfilled = self.fulfillment in FULFILLED_STATES
            if paid and fulfilled:
                return "WON_COMPLETED"
            if paid and not fulfilled:
                return "WON_PAID_NOT_DELIVERED"
            return "WON_NOT_FULFILLED"
        if self.deal in (DealState.DECLINED_BY_CLIENT, DealState.LOST,
                         DealState.EXPIRED):
            return "LOST_WITH_REASON"      # reason enforced by invariant
        if self.lead is LeadState.DISQUALIFIED:
            return "DISQUALIFIED_WITH_REASON"
        return None

    def is_commercially_won(self) -> bool:
        return self.deal in DEAL_POSITIVE

    def payment_settled(self) -> bool:
        return self.transaction in PAID_STATES

    def fulfillment_settled(self) -> bool:
        return self.fulfillment in FULFILLED_STATES

    def business_language(self) -> str:
        """Dashboard semantics: never show 'won' as finished when money or
        delivery is still open."""
        view = self.derived_outcome_view()
        if view == "WON_NOT_FULFILLED":
            if self.transaction in (TransactionState.PAYMENT_PENDING,
                                    TransactionState.INVOICE_ISSUED,
                                    TransactionState.INVOICE_REQUIRED,
                                    TransactionState.INVOICE_DRAFTED):
                return ("Client accepted, but payment is still pending. "
                        "This case is not complete yet.")
            if self.transaction is TransactionState.PAYMENT_OVERDUE:
                return ("Client accepted, but payment is overdue — "
                        "handle before anything else.")
            if self.transaction is TransactionState.PAYMENT_FAILED:
                return ("Client accepted, but the payment failed. "
                        "This case is not complete yet.")
            return ("Client accepted, but delivery/service is still open. "
                    "This case is not complete yet.")
        if view == "WON_PAID_NOT_DELIVERED":
            return ("Paid, but not yet delivered — schedule and complete "
                    "the work.")
        if view == "WON_COMPLETED":
            return "Fully won: accepted, settled, delivered."
        if view == "LOST_WITH_REASON":
            return "Not won — reason recorded, recovery may apply."
        return "Case in progress."
