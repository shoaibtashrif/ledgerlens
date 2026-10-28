# 5-Minute Demo Video Script & Walkthrough Guide

Use this script when recording your 5-minute video on Loom. It directly answers all evaluation rubric criteria.

---

## ⏱️ Video Timeline & Talking Points

### 00:00 – 00:45: The Problem & Baseline (Why We Built This)
- **Visual**: Start on the LedgerLens home screen or show a sample invoice PDF.
- **Script**:
  > *"Hi, I'm presenting LedgerLens, an autonomous Accounts Payable and invoice copilot.
  > Small business operators and finance managers spend 3 to 5 minutes manually typing every vendor bill into spreadsheets.
  > When teams try using raw ChatGPT, it frequently hallucinates numbers, accepts bad math, and has zero memory of duplicate invoices.
  > We set out to build a production system that automates invoice ingestion while enforcing deterministic arithmetic proofs, duplicate detection, and a human-in-the-loop review queue."*

---

### 00:45 – 02:00: Live End-to-End Flow (Happy Path)
- **Visual**: 
  1. Click **"Quick Test with Built-in Samples"** on `01_clean_aws_cloud_invoice.pdf`.
  2. Watch the live progress indicator complete in ~1.5 seconds.
  3. Show the document appearing as **`auto_approved`** with 85%+ confidence.
- **Script**:
  > *"Let's test a clean digital invoice from AWS. Notice that digital PDFs extract text directly using PyMuPDF—meaning zero token latency and 100% exact character transcription.
  > Within 1.5 seconds, Groq and our Pydantic contracts extract the vendor name, invoice date, currency, and line items.
  > Because our deterministic math validation confirmed that subtotal plus tax equals the total, and there are no duplicate matches, the document is automatically approved and placed directly onto our general ledger."*

---

### 02:00 – 03:15: Non-Developer Experience & API Key Setup
- **Visual**:
  1. Click the **"API Keys & Models"** button in the top navigation.
  2. Show the settings modal: direct links to "Get Groq API Key" / "Get OpenAI API Key", live password input, and the "Test & Save" button.
  3. Show the provider status badges in the top right.
  4. Navigate to **"Verified Ledger"** tab and click **"Export Excel (.xlsx)"** to demonstrate instant download.
- **Script**:
  > *"We designed this so any non-developer can run it immediately without touching terminal config files.
  > In the settings modal, users can click direct links to generate an API key, paste it, and test it live.
  > LedgerLens supports Groq's high-speed Qwen 27B LPU, OpenAI's GPT-4o-mini, and 100% offline local models via Ollama.
  > Once approved, operators can export professional multi-tab Excel workbooks complete with ledger entries, line items, and monthly category summaries with a single click."*

---

### 03:15 – 04:15: Failure Handling & Human-in-the-Loop Review
- **Visual**:
  1. Click sample `06_edge_math_mismatch_hardware.pdf`.
  2. Show the status immediately changing to **`needs_review`**.
  3. Switch to the **"Review Queue"** tab.
  4. Click **"Review & Fix"** to open the side-by-side drawer: show the PDF on the left and the flagged error message on the right:
     *"[ERROR] Subtotal 1,800.00 + tax 180.00 = 1,980.00, but total says 2,450.00."*
  5. Demonstrate typing the corrected amount in the form and clicking **"Verify & Approve to Ledger"**.
  6. Click sample `08_edge_duplicate_aws_invoice.pdf` to show duplicate detection in action.
- **Script**:
  > *"Now let's deliberately try to break the system. This Dell invoice lists subtotal $1,800 and tax $180, but a printed total of $2,450.
  > A raw LLM would blindly accept this $470 error. But LedgerLens catches the arithmetic mismatch in deterministic code, reduces confidence, and routes it to our human review drawer.
  > The operator sees the document on the left, the exact error flagged on the right, corrects the number, and approves it.
  > Furthermore, when an invoice is resubmitted, our duplicate engine checks the file hash and normalized vendor index to prevent double payment."*

---

### 04:15 – 05:00: Evaluation Benchmark, Limitations & Conclusion
- **Visual**:
  1. Switch to the **"Analytics & ROI"** tab: show the Straight-Through Rate (70%), Manual Touch Rate (30%), Average Latency, and Cost.
  2. Switch to the **"Audit & Logs"** tab: show the real-time execution trace.
- **Script**:
  > *"We proved LedgerLens is superior through an automated benchmark of 10 representative test cases.
  > While manual processing takes over 3 minutes per invoice, LedgerLens processes invoices in under 2 seconds—an over 90% time reduction.
  > It achieved a 100% catch rate on arithmetic mismatches, duplicate entries, and non-invoice contracts.
  > The primary limitation today is very blurry mobile camera receipts, which we mitigate through our human review queue.
  > In the next two weeks, we plan to add automated Gmail inbox polling and direct QuickBooks synchronization.
  > Thank you!"*
