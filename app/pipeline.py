"""Orchestrates: ingest → extract → validate → (second opinion) → categorize → decide → save."""
from __future__ import annotations

import time
import uuid
from pathlib import Path

from . import ingest
from .config import settings
from .extract import ExtractionError, extract
from .schemas import InvoiceData, Issue
from .store import Store, now
from .validate import (categorize, confidence, decide_status, norm_invoice_no,
                       norm_vendor, validate)

SECOND_OPINION_CODES = {"total_mismatch", "missing_required", "bad_date", "future_date"}
ACTIVE = ["auto_approved", "needs_review", "approved"]


def find_duplicates(store: Store, data: InvoiceData, file_hash: str, self_id: str) -> list[dict]:
    out = []
    v, n = norm_vendor(data.vendor_name), norm_invoice_no(data.invoice_number)
    for d in store.list(ACTIVE, limit=5000):
        if d["id"] == self_id:
            continue
        if d["file_hash"] == file_hash:
            out.append({"filename": d["filename"], "reason": "identical file"})
            continue
        o = d.get("data") or {}
        if not v or norm_vendor(o.get("vendor_name")) != v:
            continue
        if n and norm_invoice_no(o.get("invoice_number")) == n:
            out.append({"filename": d["filename"], "reason": "same vendor + invoice number"})
        elif data.total is not None and o.get("total") == data.total and o.get("invoice_date") == data.invoice_date:
            out.append({"filename": d["filename"], "reason": "same vendor, date and total"})
    return out


def _score(issues: list[Issue], data: InvoiceData) -> tuple:
    return (sum(i.severity == "error" for i in issues), sum(i.severity == "warning" for i in issues), -data.model_confidence)


def evaluate(store: Store, data: InvoiceData, file_hash: str, doc_id: str, kind: str, run_checks: bool = True):
    if not run_checks:                       # "naive" baseline mode for evaluation
        cat, src = categorize(data)
        return [], cat, src, data.model_confidence, ("rejected" if not data.is_invoice else "auto_approved")
    issues = validate(data, find_duplicates(store, data, file_hash, doc_id))
    cat, src = categorize(data)
    if cat is None and data.is_invoice:
        issues.append(Issue(code="uncategorized", severity="warning", message="Could not pick a category.", field="category"))
    conf = confidence(data, issues, kind)
    return issues, cat, src, conf, decide_status(issues, conf)


def process_file(store: Store, path: Path, filename: str, only: str | None = None,
                 run_checks: bool = True, doc_id: str | None = None) -> dict:
    doc_id = doc_id or uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    trace: list[dict] = []
    rec: dict = {"id": doc_id, "filename": filename, "stored_path": str(path), "created_at": now(),
                 "file_hash": ingest.sha256(path) if path.exists() else None, "attempts": 0,
                 "tokens_in": 0, "tokens_out": 0, "cost_usd": None}
    store.log(doc_id, "info", "start", f"Processing {filename}")
    try:
        doc = ingest.load(path)
        rec["kind"] = doc.kind
        trace.append({"step": "ingest", "ok": True, "kind": doc.kind, "pages": doc.pages, "note": doc.note})
        store.log(doc_id, "info", "ingest", f"{doc.kind} mode, {doc.pages} page(s). {doc.note}".strip())

        data, res, attempts = extract(doc, trace, only=only)
        results = [(data, res)]
        rec["attempts"] = attempts
        issues, cat, src, conf, status = evaluate(store, data, rec["file_hash"], doc_id, doc.kind, run_checks)

        # Second opinion: suspicious result? ask the next provider and keep the better extraction.
        if (run_checks and not only and settings.pipeline["second_opinion"]
                and any(i.code in SECOND_OPINION_CODES for i in issues)):
            try:
                alt, alt_res, alt_attempts = extract(doc, trace, exclude={res.provider})
                rec["attempts"] += alt_attempts
                results.append((alt, alt_res))
                a = evaluate(store, alt, rec["file_hash"], doc_id, doc.kind)
                better = _score(a[0], alt) < _score(issues, data)
                trace.append({"step": "second_opinion", "ok": True, "provider": alt_res.provider,
                              "kept": "second" if better else "first"})
                store.log(doc_id, "info", "second_opinion", f"Checked with {alt_res.provider}; kept {'second' if better else 'first'} result.")
                if better:
                    data, res = alt, alt_res
                    issues, cat, src, conf, status = a
            except ExtractionError as e:
                trace.append({"step": "second_opinion", "ok": False, "error": str(e)[:200]})

        costs = [r.cost_usd for _, r in results if r.cost_usd is not None]
        rec.update({
            "status": status, "data": data.model_dump(), "original": data.model_dump(),
            "category": cat, "category_source": src, "issues": [i.model_dump() for i in issues],
            "confidence": conf, "provider": res.provider, "model": res.model,
            "tokens_in": sum(r.tokens_in for _, r in results), "tokens_out": sum(r.tokens_out for _, r in results),
            "cost_usd": round(sum(costs), 6) if costs else None,
        })
        trace.append({"step": "validate", "ok": True, "errors": sum(i.severity == "error" for i in issues),
                      "warnings": sum(i.severity == "warning" for i in issues)})
        store.log(doc_id, "warning" if status != "auto_approved" else "info", "decide",
                  f"{status} (confidence {conf:.2f}, {len(issues)} issue(s)) via {res.provider}/{res.model}")
    except (ingest.IngestError, ExtractionError) as e:
        step = "ingest" if isinstance(e, ingest.IngestError) else "extract"
        rec.update({"status": "failed", "confidence": 0.0,
                    "issues": [{"code": f"{step}_failed", "severity": "error", "message": str(e), "field": None}]})
        trace.append({"step": step, "ok": False, "error": str(e)})
        store.log(doc_id, "error", step, str(e))
    except Exception as e:  # noqa: BLE001 - never crash the UI; record it
        rec.update({"status": "failed", "confidence": 0.0,
                    "issues": [{"code": "internal_error", "severity": "error", "message": f"Unexpected error: {e}", "field": None}]})
        trace.append({"step": "internal", "ok": False, "error": repr(e)[:300]})
        store.log(doc_id, "error", "internal", repr(e)[:300])

    rec["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    rec["trace"] = trace
    store.save(rec)
    return store.get(doc_id)


def apply_review(store: Store, doc_id: str, data: dict, category: str | None, action: str, note: str | None) -> dict:
    """Human edits → re-validate → approve/reject. Records which fields the human changed."""
    rec = store.get(doc_id)
    if rec is None:
        raise KeyError(doc_id)
    new = InvoiceData.model_validate({**(rec.get("data") or {}), **data})
    original = rec.get("original") or {}
    edited = [k for k, v in new.model_dump().items()
              if k not in {"model_confidence", "notes", "suggested_category"} and original.get(k) != v]
    if category and category != rec.get("category"):
        edited.append("category")
    issues = validate(new, find_duplicates(store, new, rec["file_hash"], doc_id))
    status = {"approve": "approved", "reject": "rejected"}.get(action, rec["status"])
    store.update(doc_id, data=new.model_dump(), category=category or rec.get("category"),
                 category_source="human" if "category" in edited else rec.get("category_source"),
                 issues=[i.model_dump() for i in issues], status=status, edited_fields=edited,
                 reviewer_note=note, reviewed_at=now())
    store.log(doc_id, "info", "review", f"{action} by reviewer; edited: {', '.join(edited) or 'nothing'}")
    return store.get(doc_id)
