# AI Collaboration Note

## 1. AI Tools Used & Roles

| Tool / Model | Primary Role | Rationale |
|---|---|---|
| **Google Antigravity / Gemini / Claude** | Pair-programming architect & assistant | Code generation, test suite scaffolding, and refactoring assistance. |
| **Groq (Qwen 3.8 27B)** | Primary production inference model | Ultra-fast LPU inference (1.2s - 1.8s per invoice) with multimodal vision and document understanding. |
| **OpenAI (GPT-4o-mini)** | Secondary cloud fallback & second opinion | High semantic reasoning for complex multiline tables; serves as fallback when Groq hits rate limits. |
| **Ollama (Qwen 2.5 local)** | Offline privacy fallback | Zero-cost local inference for air-gapped or sensitive financial records. |

---

## 2. Work Delegated to AI

- **Boilerplate API Scaffolding**: Fast generation of standard FastAPI endpoints and SQLite table schemas.
- **Visual Frontend Layout**: Building responsive CSS stylesheets, modal markup, and SVG icons.
- **Multimodal Visual Extraction**: Transcribing unstructured layout text and handwritten receipts into structured JSON data.
- **Synthetic Test Data Generation**: Generating edge-case invoice templates and test scenarios across different industries (SaaS, travel, telecom, consulting).

---

## 3. How AI-Generated Results Were Verified

1. **Pydantic Schema Validation**: Every model output was validated against a strict Pydantic model (`schemas.InvoiceData`). Unparseable responses triggered automated repair turns.
2. **Deterministic Arithmetic Proofing**: We wrote Python code to independently verify `subtotal + tax == total ± tolerance`. We never trusted the model's assertion that its math was correct.
3. **Automated Benchmark Matrix (`eval/run_eval.py`)**: All 10 test cases were executed against ground truth with automated scoring of field matches, status matches, and error codes.
4. **Interactive Side-by-Side Review**: We tested the web UI on real PDF documents, rendering the original file inside an iframe directly beside the extracted fields to verify character-by-character accuracy.

---

## 4. Important Results Rejected or Manually Corrected

- **Rejected Prompt-Based Math Verification**: An initial AI-generated prompt asked the model: *"Check if line items sum to subtotal and explain errors."* The LLM routinely hallucinated that the math was correct on flawed documents because of probability smoothing. **Decision**: Completely removed arithmetic validation from the prompt; delegated 100% of arithmetic verification to deterministic Python code.
- **Rejected Heavy Autonomous Frameworks (Hermes Agent / LangChain)**: Initial discussions considered using autonomous agent loops. Autonomous agents produced non-deterministic execution times (sometimes taking 45 seconds for a simple PDF) and introduced unstable tool-calling errors. **Decision**: Replaced with a linear, deterministic pipeline with explicit fallback.
- **Rejected Image-Only Ingestion**: An early code suggestion routed all PDF files through PDF-to-image rendering before calling the vision model. This consumed 2,000+ vision tokens per page and took 3x longer. **Decision**: Implemented smart ingestion in `ingest.py` where digital PDFs extract text directly via PyMuPDF in under 10ms at $0.00 cost.
- **Corrected Date Parsing Ambiguity**: Models frequently extracted dates like `"03/04/2026"` ambiguously (March 4 vs April 3). **Decision**: Built a multi-format date parser in `validate.py` that checks for invoice date vs due date sequencing and flags ambiguous entries.

---

## 5. Core Decisions Personally Owned

1. **Problem & Domain Selection**: Selected the Accounts Payable invoice bottleneck over alternative ideas because it represents a recurring, measurable pain point with immediate business ROI and verifiable ground truth.
2. **Deterministic Guardrails Architecture**: Designed the hybrid architecture where AI handles perception/extraction, while deterministic code owns validation, arithmetic proofs, duplicate checks, and status decisions.
3. **Zero-Setup Non-Developer UX**: Personally mandated that the application must run with a single command (`python run.py`) and allow users to enter and test API keys directly in the browser UI without touching terminal configuration files.
4. **Evaluation Rubric & Benchmark Design**: Formulated the 10-case test matrix covering clean, noisy, arithmetic mismatch, duplicate, foreign currency, and non-invoice scenarios to ensure honest, reproducible proof of superiority over raw LLM baselines.
