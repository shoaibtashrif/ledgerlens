"""Configuration: YAML settings + .env secrets + runtime overrides from the UI."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv, set_key, unset_key

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
CONFIG_PATH = ROOT / "config" / "settings.yaml"
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
RUNTIME_PATH = DATA_DIR / "runtime.json"
DB_PATH = Path(os.getenv("LEDGERLENS_DB", DATA_DIR / "ledgerlens.db"))

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
load_dotenv(ENV_PATH)


class Settings:
    """Single source of truth for config. Keys pasted in the UI live in memory
    (and optionally in .env when the user ticks "remember")."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.raw: dict = yaml.safe_load(CONFIG_PATH.read_text())
        self.runtime: dict = {}
        if RUNTIME_PATH.exists():
            try:
                self.runtime = json.loads(RUNTIME_PATH.read_text())
            except json.JSONDecodeError:
                self.runtime = {}
        self._keys: dict[str, str] = {}
        self._ollama_cache: tuple[float, list[str] | None] = (0.0, None)

    # ---- sections -------------------------------------------------------
    @property
    def app(self) -> dict:
        return self.raw["app"]

    @property
    def pipeline(self) -> dict:
        return self.raw["pipeline"]

    @property
    def validation(self) -> dict:
        return self.raw["validation"]

    @property
    def categories(self) -> dict[str, list[str]]:
        return self.raw["categories"]

    @property
    def provider_order(self) -> list[str]:
        return self.raw["providers"]["order"]

    def provider(self, name: str) -> dict:
        cfg = dict(self.raw["providers"][name])
        cfg.update(self.runtime.get("models", {}).get(name, {}))
        cfg["name"] = name
        return cfg

    # ---- keys -----------------------------------------------------------
    def get_key(self, name: str) -> str | None:
        cfg = self.raw["providers"][name]
        return self._keys.get(name) or os.getenv(cfg["key_env"]) or None

    def set_key(self, name: str, key: str, remember: bool) -> None:
        cfg = self.raw["providers"][name]
        with self._lock:
            self._keys[name] = key
            if remember:
                ENV_PATH.touch(exist_ok=True)
                set_key(str(ENV_PATH), cfg["key_env"], key)
                os.environ[cfg["key_env"]] = key

    def clear_key(self, name: str) -> None:
        cfg = self.raw["providers"][name]
        with self._lock:
            self._keys.pop(name, None)
            os.environ.pop(cfg["key_env"], None)
            if ENV_PATH.exists():
                unset_key(str(ENV_PATH), cfg["key_env"])

    def set_models(self, name: str, text_model: str | None, vision_model: str | None) -> None:
        with self._lock:
            models = self.runtime.setdefault("models", {})
            models[name] = {"text_model": text_model or None, "vision_model": vision_model or None}
            RUNTIME_PATH.write_text(json.dumps(self.runtime, indent=2))

    # ---- availability ---------------------------------------------------
    def ollama_models(self) -> list[str] | None:
        """Installed Ollama models, or None if Ollama is not running (cached 20s)."""
        ts, cached = self._ollama_cache
        if time.time() - ts < 20:
            return cached
        base = self.raw["providers"]["ollama"]["base_url"].rsplit("/v1", 1)[0]
        try:
            r = httpx.get(f"{base}/api/tags", timeout=1.5)
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
        except Exception:
            models = None
        self._ollama_cache = (time.time(), models)
        return models

    def is_available(self, name: str) -> bool:
        cfg = self.provider(name)
        if cfg.get("requires_key"):
            return bool(self.get_key(name))
        installed = self.ollama_models()
        return installed is not None and len(installed) > 0

    def model_for(self, name: str, vision: bool) -> str | None:
        cfg = self.provider(name)
        model = cfg.get("vision_model" if vision else "text_model")
        if name == "ollama" and model:
            installed = self.ollama_models() or []
            if model not in installed and f"{model}:latest" not in installed:
                return None
        return model


settings = Settings()


def mask(key: str | None) -> str | None:
    if not key:
        return None
    return key[:4] + "…" + key[-4:] if len(key) > 10 else "••••"
