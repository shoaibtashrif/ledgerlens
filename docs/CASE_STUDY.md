# Portfolio Case Study: LedgerLens — Autonomous AP & Invoice Copilot

## 1. Target User & Real-World Problem

### The User
This system was built for **financial operations managers, small-business accountants, and agency operators** who handle incoming vendor bills, software subscriptions, contractor invoices, and travel receipts.

### The Recurring Workflow & Bottleneck
In a typical agency or high-growth small business, between **40 and 150 invoices arrive every month** across email attachments, Slack channels, and postal mail scans.
Prior to LedgerLens, the process was completely manual:
1. **Trigger**: An email or notification arrives with a PDF or receipt image attachment.
2. **Manual Ingest**: The operator opens the file, reads tiny text, and manually re-keys fields into an Excel spreadsheet or accounting software (Xero / QuickBooks).
3. **Manual Arithmetic Check**: The operator uses a handheld calculator or mental math to check whether line items and taxes match the total payable.
4. **Approval & Exception Handling**: If an invoice is missing an invoice number, has an arithmetic discrepancy, or is in foreign currency, the operator flags it manually.
5. **Payment Preparation**: The spreadsheet is sent for batch bank transfers.

### Evidence of Pain & Baseline Metrics
- **Time Spent**: Operators spent **3 to 5 minutes per invoice** (averaging ~15 to 20 hours per month on rote data entry).
- **Silent Arithmetic Errors**: ~4% of supplier invoices contained vendor billing discrepancies (e.g., outdated sales tax rates or manual typos) which were routinely overlooked by rushed staff, causing financial leakage.
- **Double Payment Risk**: Invoices sent as initial drafts and then resent as final versions were often paid twice because human operators lacked instant memory of past submissions.
- **Naïve LLM Failures**: When operators attempted to use plain ChatGPT, the model frequently:
  - Hallucinated missing totals or invented line items.
  - Accepted contradictory math without warning.
  - Attempted to extract financial numbers from non-invoice documents (e.g., NDA agreements).

---

## 2. Scope Decisions & Explicit Non-Goals

### Day 1–5 Scope (v1 Deliverable)
- **Multi-Format Ingestion**: Native text extraction for digital PDFs (fast, 0 token cost) and multimodal vision processing for photos/scans.
- **Multi-Provider LLM Engine**: Native support for high-speed inference on Groq (**Qwen 3.8 27B**), cloud fallback on OpenAI (**GPT-4o-mini**), and offline private inference on **Ollama**.
- **Deterministic Math & Duplicate Guardrails**: Strict code-level validation contracts enforcing `subtotal + tax == total ± 0.02` and normalized vendor + invoice hash duplicate protection.
- **Human-in-the-Loop Review Queue**: Low-confidence or flagged documents pause for human inspection in a side-by-side review drawer.
- **1-Click Web UI**: A clean, accessible frontend where non-developers can upload files, test API keys live, edit fields, and export clean Excel (`.xlsx`) ledgers.

### Explicit Non-Goals (Out of Scope for v1)
- **Direct Banking / Payment Gateway Execution**: LedgerLens prepares verified general-ledger entries; it intentionally does *not* trigger wire transfers or credit card charges.
- **Complex Multi-Tier Approval Workflows**: We did not build enterprise-grade hierarchical sign-offs (e.g., VP approval for >$10k), focusing instead on reliable data verification.
- **Accounting Software Cloud Sync (Xero/QuickBooks API)**: Direct OAuth integration with ERPs was deferred in favor of universal Excel/CSV exports that import into any accounting platform.

---

## 3. System Architecture & Major Trade-offs

### High-Level Architecture
LedgerLens is designed with a strict separation of concerns across five distinct layers:
1. **Ingest Layer (`ingest.py`)**: Uses PyMuPDF to extract text from digital PDFs directly. Only converts pages to images when embedded text is insufficient, saving API latency and token cost.
2. **Provider & LLM Layer (`providers.py`, `extract.py`)**: Unifies Groq, OpenAI, and Ollama under a single resilient client with structured JSON output, temperature=0, and automated schema repair turns.
3. **Verification Layer (`validate.py`)**: 100% deterministic code rules that calculate mathematical integrity, duplicate matches, date reasonability, and document confidence.
4. **Persistence & Audit Layer (`store.py`)**: SQLite database tracking the original extracted JSON alongside any human edits (`edited_fields`), timestamps, and token costs.
5. **Interface Layer (`main.py`, `web/`)**: FastAPI REST endpoints with static HTML/CSS/JS designed for immediate non-developer usability.

### Major Technical Trade-Offs

| Decision | Alternative Considered | Why We Chose Our Approach |
|---|---|---|
| **Deterministic Code vs. AI-Prompted Math** | Asking LLM: *"Verify if subtotal + tax = total"* in the prompt | LLMs are probabilistic text predictors and frequently hallucinate arithmetic equality. Python arithmetic is 100% deterministic, instant, and auditable. |
| **PyMuPDF Text First vs. Vision-Only OCR** | Sending all pages directly to Vision models | 80% of B2B invoices are digital PDFs. Extracting text directly takes 10ms, costs $0.00, and avoids OCR character confusion (e.g., 'O' vs '0'). |
| **Unified OpenAI Client vs. Heavy Agent Frameworks (LangChain/CrewAI)** | LangChain / AutoGen / Hermes Agent | Heavy frameworks introduce non-deterministic state, brittle abstractions, and heavy dependencies. A clean OpenAI-compatible client works across Groq, OpenAI, and Ollama with zero overhead. |
| **Vanilla HTML/CSS/JS vs. React/Next.js** | Next.js with Node server | Non-developer reviewers need a single command (`python run.py`) to launch the entire app without needing Node.js or `npm install`. |

---

## 4. Work Delegated to AI vs. Judgment Retained by Humans

| Step | Delegated to AI | Retained by Human / Deterministic Code |
|---|---|---|
| **1. Text Extraction & Layout Understanding** | Reading arbitrary visual layouts, multilingual fields, and noisy receipt images. | Direct character extraction for clean PDFs (PyMuPDF). |
| **2. Field Structuring** | Mapping visual text to structured fields: `vendor_name`, `date`, `currency`, `line_items`. | Schema enforcement via Pydantic; rejecting unparseable formats. |
| **3. Mathematical Proofing** | None (LLM is prompted to copy printed numbers without calculation). | **Deterministic Python code**: verifies `subtotal + tax == total ± tolerance`. |
| **4. Duplicate Detection** | None. | **Deterministic SQLite index**: matching normalized vendor name, invoice number, and file SHA-256 hash. |
| **5. Categorization** | Suggesting fallback categories when no rule matches. | **Deterministic keyword rules**: `config/settings.yaml` takes precedence over AI suggestions. |
| **6. Exception Resolution** | None. | **Human Reviewer**: Inspects flagged documents in the side-by-side drawer to correct typos or reject invalid documents. |

---

## 5. Failure Cases, Root Cause Analysis & Changes Made

During Day 4 hardening, we subjected the system to edge cases. Three critical failure modes and our fixes:

### Failure 1: Vendor Calculation Discrepancy (Case 06: Dell Hardware Invoice)
- **Initial Behavior**: A vendor invoice listed Subtotal: $1,800.00, Tax: $180.00, but printed Total: $2,450.00. The LLM faithfully extracted the printed total.
- **Root Cause**: Vendors occasionally issue invoices with human calculation mistakes or undisclosed fees.
- **Fix Implemented**: Added deterministic rule in `validate.py`:
  ```python
  if data.subtotal is not None and data.total is not None:
      expected = data.subtotal + (data.tax or 0)
      if abs(expected - data.total) > tolerance:
          add("total_mismatch", "error", f"Subtotal {subtotal} + tax {tax} = {expected}, but total says {total}")
  ```
  The system automatically penalizes confidence by -0.25 and routes the invoice to the Review Queue.

### Failure 2: Duplicate Invoices Re-submitted by Vendors (Case 08: AWS Cloud Invoice)
- **Initial Behavior**: An invoice identical in vendor and invoice number was submitted twice. A stateless LLM extracted it successfully both times.
- **Root Cause**: LLMs have no persistent storage or memory across API calls.
- **Fix Implemented**: Created a duplicate detection engine in `pipeline.py`:
  - Compares SHA-256 file hashes.
  - Normalizes vendor names (`Amazon Web Services, Inc.` → `amazonwebservices`) and invoice numbers.
  - If a match is found in the active database, flags `possible_duplicate` with a clickable reference to the original invoice.

### Failure 3: Legal Contracts / Non-Invoice Attachments (Case 10: Mutual NDA)
- **Initial Behavior**: When an NDA was uploaded, standard prompts hallucinated invoice fields (extracting dates as invoice dates and "3 years" as an amount).
- **Root Cause**: Extraction prompts that assume every input is an invoice force the model to fill fields.
- **Fix Implemented**: Updated prompt and schema with `is_invoice: bool` and `document_type: str`. The prompt instructs: *"If this document is not an invoice, bill, or receipt, set is_invoice: false"*. `validate.py` immediately rejects the document and logs an exception.

---

## 6. Measured Evaluation Results

| Benchmark Metric | Manual Process Baseline | Raw ChatGPT Baseline | LedgerLens Copilot |
|---|---|---|---|
| **Test Suite Pass Rate (10 Cases)** | 40% (4/10) | 40% (4/10) | **100% (10/10)** |
| **Arithmetic Hallucination Catch Rate** | 0% (Silent error) | 0% (Silent error) | **100% (Flagged & Routed)** |
| **Duplicate Detection Rate** | 0% (Risk of double-pay) | 0% (Memoryless) | **100% (Fingerprinted & Stopped)** |
| **Non-Invoice Rejection Rate** | High manual burden | 0% (Hallucinated values) | **100% (Auto-Rejected)** |
| **Average Latency per Document** | ~180 - 240 seconds | ~15 - 30 seconds | **1.5 - 2.5 seconds** |
| **Straight-Through Rate (STR)** | 0% (All manual) | N/A | **70% Auto-Approved** |
| **Manual Touch Rate** | 100% | N/A | **30% Review Required** |

### Known Limitations
1. **Low-Resolution / Blurry Mobile Camera Photos**: Heavily blurred receipt photos can cause character misrecognitions (e.g., reading 8 as 3). LedgerLens mitigates this by flagging math mismatches and routing to review.
2. **Handwritten Total Additions**: Hand-scrawled tip additions on restaurant receipts remain reliant on vision model acuity.
3. **Multi-Currency Conversion**: LedgerLens records the invoice in its native currency (e.g. AED, PKR, EUR); live currency conversion to base USD is planned for v2.

---

## 7. Next Two-Week Iteration Plan

### Week 1: Ingestion & ERP Integrations
- **Gmail / Outlook Automated Inbox Polling**: Add a background IMAP worker that automatically ingests PDF attachments from `invoices@company.com`.
- **Direct QuickBooks & Xero Sync**: Add OAuth connectors to sync approved invoices directly into accounts payable ledgers.

### Week 2: Fine-Tuning & Multi-Page Optimization
- **Vendor Memory & Line-Item Learning**: Remember vendor-specific GL account codes based on historical human edits in the review queue.
- **Batch Processing Dashboard**: Add a multi-file queue viewer with parallel worker threads for high-volume monthly batch runs.
