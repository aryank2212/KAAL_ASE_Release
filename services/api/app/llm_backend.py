"""Switchable LLM backend. The model host (e.g. your laptop) can run Ollama or LM Studio; KAAL talks to it over HTTP.

Config precedence: <data_dir>/llm.json (set from the dashboard / API) overrides environment defaults. It is re-read on
every call (cheap, mtime-cached), so changing the model takes effect immediately with no restart.
"""
import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.config import settings

PROVIDERS = {
    "ollama": "http://localhost:11434",
    "lmstudio": "http://localhost:1234",
}
_LOCK = threading.Lock()
_cache: dict = {"mtime": None, "cfg": None}


class LLMError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    provider: str = "ollama"
    base_url: str = PROVIDERS["ollama"]
    model: str = "gemma2:2b"
    embed_model: str = "nomic-embed-text"
    api_key: str = ""          # LM Studio / OpenAI-compatible servers may require one; Ollama does not
    timeout: int = 120

    def public(self) -> dict:
        d = asdict(self)
        d["api_key"] = "set" if self.api_key else ""
        return d


def config_path() -> Path:
    return Path(settings.data_dir).expanduser() / "llm.json"


def validate_base_url(url: str) -> str:
    u = urlparse((url or "").strip())
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
        raise LLMError("base_url must look like http://host:port (no credentials in the URL).")
    return f"{u.scheme}://{u.netloc}".rstrip("/")


def _defaults() -> LLMConfig:
    return LLMConfig(provider="ollama", base_url=settings.ollama_base_url.rstrip("/"),
                     model=settings.ollama_model, embed_model=settings.ollama_embed_model)


def current() -> LLMConfig:
    p = config_path()
    try:
        mtime = p.stat().st_mtime_ns
    except OSError:
        return _defaults()
    with _LOCK:
        if _cache["mtime"] != mtime:
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                base = asdict(_defaults())
                base.update({k: v for k, v in raw.items() if k in base})
                _cache.update(mtime=mtime, cfg=LLMConfig(**base))
            except (OSError, ValueError, TypeError):
                return _defaults()
        return _cache["cfg"]


def save(cfg: LLMConfig) -> None:
    if cfg.provider not in PROVIDERS:
        raise LLMError(f"provider must be one of {sorted(PROVIDERS)}")
    cfg.base_url = validate_base_url(cfg.base_url)
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with _LOCK:
        tmp.write_text(json.dumps(asdict(cfg)), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)           # may hold an API key
        except OSError:
            pass
        tmp.replace(p)
        _cache["mtime"] = None


def _headers(cfg: LLMConfig) -> dict:
    return {"Authorization": f"Bearer {cfg.api_key}"} if cfg.api_key else {}


def _request(cfg: LLMConfig, method: str, path: str, timeout: float | None = None, **kw) -> dict:
    try:
        r = httpx.request(method, cfg.base_url + path, headers=_headers(cfg), timeout=timeout or cfg.timeout, **kw)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        raise LLMError(f"{cfg.provider} at {cfg.base_url} answered HTTP {e.response.status_code} for {path}")
    except httpx.HTTPError as e:
        raise LLMError(f"cannot reach {cfg.provider} at {cfg.base_url} ({type(e).__name__}). "
                       "Is it running and listening on the network (not just localhost)?")
    except ValueError:
        raise LLMError(f"{cfg.provider} returned a non-JSON response for {path}")


def list_models(cfg: LLMConfig | None = None) -> list[dict]:
    cfg = cfg or current()
    if cfg.provider == "ollama":
        data = _request(cfg, "GET", "/api/tags", timeout=10)
        names = [m.get("name") or m.get("model") for m in data.get("models", [])]
    else:
        data = _request(cfg, "GET", "/v1/models", timeout=10)
        names = [m.get("id") for m in data.get("data", [])]
    return [{"name": n, "embedding": "embed" in n.lower()} for n in names if n]


def chat(system: str, prompt: str, model: str | None = None, temperature: float = 0.1) -> str:
    cfg = current()
    model = model or cfg.model
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    if cfg.provider == "ollama":
        data = _request(cfg, "POST", "/api/chat", json={"model": model, "stream": False, "messages": msgs,
                                                        "options": {"temperature": temperature}})
        try:
            return data["message"]["content"]
        except (KeyError, TypeError):
            raise LLMError("unexpected reply from Ollama /api/chat")
    data = _request(cfg, "POST", "/v1/chat/completions",
                    json={"model": model, "stream": False, "messages": msgs, "temperature": temperature})
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise LLMError("unexpected reply from the OpenAI-compatible /v1/chat/completions")


def embed(text: str) -> list[float]:
    cfg = current()
    if cfg.provider == "ollama":
        data = _request(cfg, "POST", "/api/embeddings", timeout=30, json={"model": cfg.embed_model, "prompt": text})
        return data["embedding"]
    data = _request(cfg, "POST", "/v1/embeddings", timeout=30, json={"model": cfg.embed_model, "input": text})
    return data["data"][0]["embedding"]


def status() -> dict:
    cfg = current()
    t = time.time()
    try:
        models = list_models(cfg)
    except LLMError as e:
        return {"config": cfg.public(), "reachable": False, "error": str(e), "models": []}
    names = {m["name"] for m in models}
    return {"config": cfg.public(), "reachable": True, "latency_ms": int((time.time() - t) * 1000),
            "model_available": cfg.model in names, "models": models}
