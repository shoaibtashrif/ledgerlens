"""Turn an uploaded file into either text (digital PDF) or page images (scans/photos)."""
from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError

from .config import settings

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
MAX_SIDE = 1200


class IngestError(Exception):
    """User-facing ingest problem (bad file, too big, encrypted...)."""


@dataclass
class Document:
    kind: str                       # "text" | "vision"
    pages: int
    text: str = ""
    images: list[str] = field(default_factory=list)   # base64 JPEG
    note: str = ""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _encode(img: Image.Image) -> str:
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def load(path: Path) -> Document:
    size_mb = path.stat().st_size / 1e6
    if size_mb > settings.app["max_file_mb"]:
        raise IngestError(f"File is {size_mb:.1f} MB; the limit is {settings.app['max_file_mb']} MB.")
    if size_mb == 0:
        raise IngestError("File is empty.")

    ext = path.suffix.lower()
    max_pages = settings.app["max_pages"]

    if ext == ".pdf":
        try:
            pdf = pymupdf.open(path)
        except Exception as e:  # noqa: BLE001
            raise IngestError("This PDF is damaged or not a real PDF.") from e
        if pdf.needs_pass:
            raise IngestError("This PDF is password-protected. Remove the password and upload again.")
        text = "\n\n".join(f"--- page {i + 1} ---\n{p.get_text()}" for i, p in enumerate(pdf))
        if len(text.replace("--- page", "").strip()) >= settings.app["text_pdf_min_chars"]:
            return Document(kind="text", pages=pdf.page_count, text=text[:20000])
        images = []
        for page in list(pdf)[:max_pages]:
            pix = page.get_pixmap(dpi=150)
            images.append(_encode(Image.open(io.BytesIO(pix.tobytes("png")))))
        note = f"Only first {max_pages} of {pdf.page_count} pages sent." if pdf.page_count > max_pages else ""
        return Document(kind="vision", pages=pdf.page_count, images=images, note=note)

    if ext in IMAGE_EXT:
        try:
            img = Image.open(path)
            img.load()
        except (UnidentifiedImageError, OSError) as e:
            raise IngestError("Cannot read this image (corrupted or unsupported format).") from e
        frames = getattr(img, "n_frames", 1)
        images = []
        for i in range(min(frames, max_pages)):
            img.seek(i)
            images.append(_encode(img.copy()))
        return Document(kind="vision", pages=frames, images=images)

    if ext in {".heic", ".heif"}:
        raise IngestError("HEIC photos are not supported yet. Export as JPG or PNG first.")
    raise IngestError(f"Unsupported file type '{ext or 'none'}'. Upload a PDF, JPG, PNG or WEBP.")
