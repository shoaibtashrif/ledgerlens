"""LLM extraction with JSON repair retries and provider fallback."""
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from .config import settings
from .ingest import Document
from .providers import LLMResult, ProviderError, candidates, chat, friendly_error
from .schemas import InvoiceData

PROMPT = """You are an accounts-payable data-extraction engine.
Extract the fields from the document and return ONLY a JSON object with exactly these keys:

{{
  "is_invoice": true,                 // false if this is NOT an invoice / receipt / bill
  "document_type": "invoice",         // invoice | receipt | bill | credit_note | other
  "vendor_name": "string or null",    // the company that issued the document (seller), not the customer
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "currency": "ISO 4217 code or null",// infer from symbols: $=USD, €=EUR, £=GBP, Rs/PKR=PKR, AED, INR
  "subtotal": number or null,
  "tax": number or null,              // total tax/VAT/GST amount
  "total": number or null,            // final amount payable
  "line_items": [{{"description": "string", "quantity": number|null, "unit_price": number|null, "amount": number|null}}],
  "suggested_category": one of {categories},
  "model_confidence": number,         // 0-1: how sure you are that ALL fields are correct
  "notes": "string or null"           // anything unclear: blurry, cut off, handwritten, multiple totals
}}

Rules:
- Copy values exactly as printed. If a value is not visible, use null. NEVER guess or compute missing values.
- Numbers: plain JSON numbers, no currency symbols, no thousands separators (1.234,56 EUR -> 1234.56).
- Dates: convert to YYYY-MM-DD. If day/month order is ambiguous, say so in notes.
- Lower model_confidence for blurry, rotated, handwritten or partially visible documents.
- Output JSON only. No markdown, no explanation."""


class ExtractionError(Exception):
    pass


def parse_json(content: str) -> dict:
    s = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
    s = re.sub(r"^```(?:json)?|```$", "", s, flags=re.M).strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    return json.loads(s[start : end + 1])


def build_messages(doc: Document) -> list[dict]:
    instructions = PROMPT.format(categories=json.dumps(list(settings.categories)))
    if doc.kind == "text":
        return [{"role": "user", "content": f"{instructions}\n\nDocument text (extracted from a digital PDF):\n<<<\n{doc.text}\n>>>"}]
    # Instructions live in the user turn: some vision endpoints reject system prompts with images.
    parts: list[dict] = [{"type": "text", "text": instructions + f"\n\nThe document has {len(doc.images)} page image(s)."}]
    parts += [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in doc.images]
    return [{"role": "user", "content": parts}]


def extract(doc: Document, trace: list[dict], only: str | None = None,
            exclude: set[str] | None = None) -> tuple[InvoiceData, LLMResult, int]:
    vision = doc.kind == "vision"
    cands = candidates(vision, only=only, exclude=exclude)
    if not cands:
        if vision:
            raise ExtractionError("Scanned/photo documents need a vision model. Add a Groq or OpenAI key in Settings.")
        raise ExtractionError("No AI provider is configured. Add a Groq or OpenAI key in Settings.")

    max_attempts = settings.pipeline["max_attempts_per_provider"]
    errors: list[str] = []
    total_attempts = 0
    for name, model in cands:
        label = settings.provider(name)["label"]
        messages = build_messages(doc)
        for attempt in range(1, max_attempts + 1):
            total_attempts += 1
            try:
                res = chat(name, model, messages)
            except ProviderError as e:
                errors.append(str(e))
                trace.append({"step": "extract", "provider": name, "model": model, "ok": False, "error": str(e)})
                break
            except Exception as e:  # noqa: BLE001 - network/API errors -> next provider
                msg = friendly_error(e, label)
                errors.append(msg)
                trace.append({"step": "extract", "provider": name, "model": model, "ok": False, "error": msg})
                break
            try:
                data = InvoiceData.model_validate(parse_json(res.content))
                trace.append({"step": "extract", "provider": name, "model": model, "ok": True,
                              "attempt": attempt, "latency_ms": res.latency_ms,
                              "tokens": res.tokens_in + res.tokens_out})
                return data, res, total_attempts
            except (ValueError, ValidationError) as e:
                err = str(e).splitlines()[0][:200]
                trace.append({"step": "extract", "provider": name, "model": model, "ok": False,
                              "attempt": attempt, "error": f"invalid output: {err}"})
                messages = messages + [
                    {"role": "assistant", "content": res.content[:4000]},
                    {"role": "user", "content": f"That output was invalid ({err}). Return ONLY the corrected JSON object."},
                ]
        else:
            errors.append(f"{label}: returned invalid JSON {max_attempts} times")
    raise ExtractionError("All AI providers failed → " + " | ".join(errors))
