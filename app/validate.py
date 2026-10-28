"""Deterministic checks — the part that catches what a plain chatbot misses."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from .config import settings
from .schemas import InvoiceData, Issue

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y"]
COMPANY_SUFFIX = r"\b(inc|llc|ltd|limited|pvt|private|co|corp|corporation|gmbh|plc|company)\b"


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def norm_vendor(s: str | None) -> str:
    s = (s or "").lower()
    s = re.sub(COMPANY_SUFFIX, "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def norm_invoice_no(s: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper()).lstrip("0")


def validate(data: InvoiceData, duplicates: list[dict] | None = None, today: date | None = None) -> list[Issue]:
    v = settings.validation
    tol = v["amount_tolerance"]
    today = today or date.today()
    issues: list[Issue] = []

    def add(code, severity, message, field=None):
        issues.append(Issue(code=code, severity=severity, message=message, field=field))

    if not data.is_invoice or data.document_type == "other":
        add("not_invoice", "error", "This does not look like an invoice, receipt or bill.")
        return issues

    for f in v["required_fields"]:
        if getattr(data, f) in (None, ""):
            add("missing_required", "error", f"Required field '{f}' could not be read.", f)

    if not data.invoice_number:
        add("missing_invoice_number", "warning", "No invoice number — duplicate detection is weaker.", "invoice_number")
    if not data.currency:
        add("missing_currency", "warning", f"Currency not found; assuming {settings.app['base_currency']}.", "currency")
    elif data.currency != settings.app["base_currency"]:
        add("foreign_currency", "info", f"Amount is in {data.currency}, not {settings.app['base_currency']}.", "currency")

    d = parse_date(data.invoice_date)
    if data.invoice_date and not d:
        add("bad_date", "error", f"Invoice date '{data.invoice_date}' is not a valid date.", "invoice_date")
    if d:
        if d > today + timedelta(days=1):
            add("future_date", "error", f"Invoice date {d} is in the future.", "invoice_date")
        elif (today - d).days > v["max_age_days"]:
            add("old_invoice", "warning", f"Invoice is {(today - d).days} days old.", "invoice_date")
    due = parse_date(data.due_date)
    if d and due and due < d:
        add("due_before_issue", "warning", "Due date is before the invoice date.", "due_date")

    if data.total is not None:
        if data.total == 0:
            add("zero_total", "warning", "Total is 0.", "total")
        elif data.total < 0:
            add("negative_total", "warning", "Negative total — is this a credit note/refund?", "total")

    if data.subtotal is not None and data.total is not None:
        expected = data.subtotal + (data.tax or 0)
        if abs(expected - data.total) > tol:
            add("total_mismatch", "error",
                f"Subtotal {data.subtotal:,.2f} + tax {data.tax or 0:,.2f} = {expected:,.2f}, but total says {data.total:,.2f}.",
                "total")

    amounts = [li.amount for li in data.line_items if li.amount is not None]
    base = data.subtotal if data.subtotal is not None else (data.total if data.tax in (None, 0) else None)
    if amounts and base is not None and abs(sum(amounts) - base) > max(tol, 0.01 * abs(base)):
        add("line_items_mismatch", "warning",
            f"Line items add up to {sum(amounts):,.2f}, but subtotal is {base:,.2f}.", "line_items")

    for dup in duplicates or []:
        add("possible_duplicate", "error",
            f"Possible duplicate of '{dup['filename']}' ({dup['reason']}).", "invoice_number")
    return issues


def confidence(data: InvoiceData | None, issues: list[Issue], kind: str) -> float:
    """System confidence = model self-report, penalised by failed checks."""
    if data is None:
        return 0.0
    c = data.model_confidence
    if kind == "text":
        c = min(1.0, c + 0.05)          # digital text: no OCR noise
    for i in issues:
        c -= {"error": 0.25, "warning": 0.07, "info": 0.0}[i.severity]
    return round(max(0.0, min(1.0, c)), 2)


def decide_status(issues: list[Issue], conf: float) -> str:
    if any(i.code == "not_invoice" for i in issues):
        return "rejected"
    if any(i.severity == "error" for i in issues):
        return "needs_review"
    p = settings.pipeline
    if p["auto_approve"] and conf >= p["auto_approve_min_confidence"]:
        return "auto_approved"
    return "needs_review"


def categorize(data: InvoiceData) -> tuple[str | None, str]:
    """Rules first (predictable), AI suggestion second."""
    haystack = " ".join([data.vendor_name or ""] + [li.description for li in data.line_items]).lower()
    for cat, words in settings.categories.items():
        if any(w in haystack for w in words):
            return cat, "rule"
    if data.suggested_category in settings.categories:
        return data.suggested_category, "ai"
    return None, "none"
