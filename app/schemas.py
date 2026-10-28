"""Data contracts for every pipeline step."""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


def to_number(v) -> Optional[float]:
    """Coerce '1,234.50', '1.234,50', 'Rs 2,000', '(15.00)', 12 -> float."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    negative = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = re.sub(r"[^\d.,]", "", s)
    if not s or not re.search(r"\d", s):
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):          # 1.234,56 (EU)
            s = s.replace(".", "").replace(",", ".")
        else:                                     # 1,234.56
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = f"{head.replace(',', '')}.{tail}" if len(tail) == 2 else s.replace(",", "")
    elif s.count(".") > 1:                       # 1.234.567
        s = s.replace(".", "")
    try:
        n = float(s)
    except ValueError:
        return None
    return -n if negative else n


class LineItem(BaseModel):
    description: str = ""
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None

    @field_validator("quantity", "unit_price", "amount", mode="before")
    @classmethod
    def _num(cls, v):
        return to_number(v)

    @field_validator("description", mode="before")
    @classmethod
    def _desc(cls, v):
        return "" if v is None else str(v)


class InvoiceData(BaseModel):
    """What the model must return. Missing values must be null, never guessed."""
    is_invoice: bool = True
    document_type: str = "invoice"            # invoice | receipt | bill | other
    vendor_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None        # YYYY-MM-DD
    due_date: Optional[str] = None
    currency: Optional[str] = None            # ISO 4217
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    line_items: list[LineItem] = Field(default_factory=list)
    suggested_category: Optional[str] = None
    model_confidence: float = 0.5
    notes: Optional[str] = None

    @field_validator("subtotal", "tax", "total", mode="before")
    @classmethod
    def _num(cls, v):
        return to_number(v)

    @field_validator("model_confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        n = to_number(v)
        if n is None:
            return 0.5
        if n > 1:                                  # model answered 85 instead of 0.85
            n = n / 100
        return max(0.0, min(1.0, n))

    @field_validator("currency", mode="before")
    @classmethod
    def _cur(cls, v):
        if not v:
            return None
        s = str(v).strip().upper()
        symbols = {"$": "USD", "€": "EUR", "£": "GBP", "RS": "PKR", "RS.": "PKR", "₨": "PKR", "AED": "AED", "¥": "JPY", "₹": "INR"}
        return symbols.get(s, s[:3] if re.fullmatch(r"[A-Z]{3}.*", s) else s)

    @field_validator("vendor_name", "invoice_number", "invoice_date", "due_date", "notes", mode="before")
    @classmethod
    def _str(cls, v):
        if v is None:
            return None
        s = str(v).strip()
        return s if s and s.lower() not in {"null", "none", "n/a", "unknown"} else None

    @field_validator("line_items", mode="before")
    @classmethod
    def _items(cls, v):
        return v if isinstance(v, list) else []


Severity = Literal["error", "warning", "info"]


class Issue(BaseModel):
    code: str
    severity: Severity
    message: str
    field: Optional[str] = None


Status = Literal["auto_approved", "needs_review", "approved", "rejected", "failed"]
