"""FastAPI backend + static web UI."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import export, pipeline
from .config import ROOT, UPLOAD_DIR, mask, settings
from .providers import ProviderError, test_key
from .store import Store

app = FastAPI(title="LedgerLens", version="1.0")
store = Store()
WEB = ROOT / "web"
SAMPLES = ROOT / "samples"


# ---------- settings / keys ----------------------------------------------
@app.get("/api/settings")
def get_settings():
    providers = []
    ollama_models = settings.ollama_models()
    for name in settings.provider_order:
        cfg = settings.provider(name)
        providers.append({
            "name": name, "label": cfg["label"], "key_url": cfg["key_url"],
            "requires_key": cfg.get("requires_key", True), "available": settings.is_available(name),
            "key_masked": mask(settings.get_key(name)), "text_model": cfg.get("text_model"),
            "vision_model": cfg.get("vision_model"),
            "installed_models": ollama_models if name == "ollama" else None,
        })
    return {"providers": providers, "categories": list(settings.categories),
            "pipeline": settings.pipeline, "validation": settings.validation, "app": settings.app}


class KeyIn(BaseModel):
    provider: str
    api_key: str
    remember: bool = True


@app.post("/api/keys")
def save_key(body: KeyIn):
    if body.provider not in settings.provider_order:
        raise HTTPException(400, "Unknown provider")
    key = body.api_key.strip()
    if len(key) < 10:
        raise HTTPException(400, "That key looks too short — copy the whole key.")
    try:
        models = test_key(body.provider, key)
    except ProviderError as e:
        raise HTTPException(400, str(e)) from e
    settings.set_key(body.provider, key, body.remember)
    store.log(None, "info", "settings", f"{body.provider} key saved (remember={body.remember})")
    return {"ok": True, "models": models}


@app.delete("/api/keys/{provider}")
def delete_key(provider: str):
    settings.clear_key(provider)
    return {"ok": True}


@app.get("/api/models/{provider}")
def list_models(provider: str):
    try:
        return {"models": test_key(provider, None)}
    except ProviderError as e:
        raise HTTPException(400, str(e)) from e


class ModelsIn(BaseModel):
    provider: str
    text_model: str | None = None
    vision_model: str | None = None


@app.post("/api/models")
def set_models(body: ModelsIn):
    settings.set_models(body.provider, body.text_model, body.vision_model)
    return {"ok": True}


# ---------- processing -----------------------------------------------------
def _store_upload(name: str, src) -> Path:
    safe = Path(name).name or "upload"
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{safe}"
    with open(dest, "wb") as out:
        shutil.copyfileobj(src, out)
    return dest


@app.post("/api/process")
def process(file: UploadFile = File(...), provider: str = Form("")):
    dest = _store_upload(file.filename or "upload", file.file)
    return pipeline.process_file(store, dest, file.filename or dest.name, only=provider or None)


@app.get("/api/samples")
def samples():
    if not SAMPLES.exists():
        return {"samples": []}
    return {"samples": sorted(p.name for p in SAMPLES.iterdir() if p.is_file() and not p.name.startswith("."))}


@app.post("/api/samples/{name}")
def process_sample(name: str):
    src = SAMPLES / Path(name).name
    if not src.exists():
        raise HTTPException(404, "Sample not found")
    with open(src, "rb") as f:
        dest = _store_upload(src.name, f)
    return pipeline.process_file(store, dest, src.name)


@app.post("/api/documents/{doc_id}/rerun")
def rerun(doc_id: str, provider: str = Form("")):
    rec = store.get(doc_id)
    if not rec:
        raise HTTPException(404, "Not found")
    return pipeline.process_file(store, Path(rec["stored_path"]), rec["filename"], only=provider or None, doc_id=doc_id)


# ---------- documents / review --------------------------------------------
@app.get("/api/documents")
def documents(status: str = ""):
    return store.list(status.split(",") if status else None)


@app.get("/api/documents/{doc_id}")
def document(doc_id: str):
    rec = store.get(doc_id)
    if not rec:
        raise HTTPException(404, "Not found")
    return rec


@app.get("/api/documents/{doc_id}/file")
def document_file(doc_id: str):
    rec = store.get(doc_id)
    if not rec or not rec.get("stored_path") or not Path(rec["stored_path"]).exists():
        raise HTTPException(404, "File not found")
    return FileResponse(rec["stored_path"])


class ReviewIn(BaseModel):
    data: dict
    category: str | None = None
    action: str = "approve"           # approve | reject | save
    note: str | None = None


@app.put("/api/documents/{doc_id}")
def review(doc_id: str, body: ReviewIn):
    try:
        return pipeline.apply_review(store, doc_id, body.data, body.category, body.action, body.note)
    except KeyError as e:
        raise HTTPException(404, "Not found") from e
    except ValueError as e:
        raise HTTPException(400, f"Invalid value: {e}") from e


@app.delete("/api/documents/{doc_id}")
def delete_doc(doc_id: str):
    store.delete(doc_id)
    return {"ok": True}


@app.post("/api/reset")
def reset():
    store.reset()
    return {"ok": True}


# ---------- reports / export / logs ----------------------------------------
@app.get("/api/report")
def report():
    ledger = store.list(export.LEDGER_STATUSES, limit=10000)
    s = export.summary(ledger)
    return {
        "metrics": export.metrics(store.list(limit=10000)),
        "by_category": [{"category": c, "currency": cur, "total": round(v, 2)} for (c, cur), v in sorted(s["by_category_currency"].items(), key=lambda x: -x[1])],
        "by_vendor": sorted(({"vendor": k, "total": round(v, 2)} for k, v in s["by_vendor"].items()), key=lambda x: -x["total"])[:10],
        "by_currency": {k: round(v, 2) for k, v in s["by_currency"].items()},
        "by_month": [{"month": m, "currency": cur, "total": round(v, 2)} for (m, cur), v in sorted(s["by_month"].items())],
    }


@app.get("/api/export.xlsx")
def export_xlsx():
    data = export.to_xlsx(store.list(export.LEDGER_STATUSES, limit=10000),
                          store.list(["needs_review", "rejected", "failed"], limit=10000))
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=ledgerlens_ledger.xlsx"})


@app.get("/api/export.csv")
def export_csv():
    return PlainTextResponse(export.to_csv(store.list(export.LEDGER_STATUSES, limit=10000)), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=ledgerlens_ledger.csv"})


@app.get("/api/logs")
def logs():
    return store.events()


@app.get("/api/health")
def health():
    return {"ok": True, "providers": {n: settings.is_available(n) for n in settings.provider_order}}


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
