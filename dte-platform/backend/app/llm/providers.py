"""LLM providers: Ollama (open-source, self-hosted) and Claude (Anthropic API).
The active provider + models are stored in app_settings['llm'] and edited from the UI (Settings → Model configuration)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import httpx

from ..config import get_settings
from ..db import AppSetting, SessionLocal, decrypt, encrypt


@dataclass
class LLMConfig:
    provider: str = "ollama"                 # "ollama" | "claude"
    ollama_url: str = ""
    ollama_model: str = ""                    # SQL / reasoning model
    ollama_embed_model: str = ""
    claude_model: str = ""                    # SQL generation (strong)
    claude_fast_model: str = ""               # intent / layout (cheap)
    anthropic_api_key: str = ""               # stored encrypted
    temperature: float = 0.0
    extra: dict = field(default_factory=dict)

    def public(self) -> dict:
        d = self.__dict__.copy()
        d["anthropic_api_key"] = ("••••" + self.anthropic_api_key[-4:]) if self.anthropic_api_key else ""
        d["has_api_key"] = bool(self.anthropic_api_key)
        return d


def load_config() -> LLMConfig:
    s = get_settings()
    cfg = LLMConfig(provider=s.default_llm_provider, ollama_url=s.ollama_url, ollama_model=s.ollama_model,
                    ollama_embed_model=s.ollama_embed_model, claude_model=s.claude_model,
                    claude_fast_model=s.claude_fast_model, anthropic_api_key=s.anthropic_api_key)
    with SessionLocal() as db:
        row = db.get(AppSetting, "llm")
        if row:
            stored = dict(row.value)
            if stored.get("anthropic_api_key_enc"):
                stored["anthropic_api_key"] = decrypt(stored.pop("anthropic_api_key_enc"))
            for k, v in stored.items():
                if hasattr(cfg, k) and v not in (None, ""):
                    setattr(cfg, k, v)
    return cfg


def save_config(update: dict) -> LLMConfig:
    cfg = load_config()
    for k, v in update.items():
        if k == "anthropic_api_key" and (not v or v.startswith("••••")):
            continue  # keep existing key when UI sends the masked value
        if hasattr(cfg, k) and v is not None:
            setattr(cfg, k, v)
    stored = {k: v for k, v in cfg.__dict__.items() if k != "anthropic_api_key"}
    stored["anthropic_api_key_enc"] = encrypt(cfg.anthropic_api_key) if cfg.anthropic_api_key else None
    with SessionLocal() as db:
        row = db.get(AppSetting, "llm")
        if row:
            row.value = stored
        else:
            db.add(AppSetting(key="llm", value=stored))
        db.commit()
    return cfg


class LLM:
    """Common interface. `tier` lets the pipeline use a cheaper model for light steps (Claude Haiku vs Sonnet)."""
    name = "base"

    def complete(self, system: str, user: str, *, json_mode: bool = False, tier: str = "strong") -> str:
        raise NotImplementedError

    def complete_json(self, system: str, user: str, *, tier: str = "strong") -> dict:
        raw = self.complete(system, user, json_mode=True, tier=tier)
        return parse_json(raw)


class OllamaLLM(LLM):
    name = "ollama"

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def complete(self, system, user, *, json_mode=False, tier="strong"):
        payload = {
            "model": self.cfg.ollama_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "options": {"temperature": self.cfg.temperature},
        }
        if json_mode:
            payload["format"] = "json"
        r = httpx.post(f"{self.cfg.ollama_url.rstrip('/')}/api/chat", json=payload, timeout=180)
        r.raise_for_status()
        return r.json()["message"]["content"]


class ClaudeLLM(LLM):
    name = "claude"

    def __init__(self, cfg: LLMConfig):
        import anthropic  # imported lazily so the open-source mode has no hard dependency on it
        if not cfg.anthropic_api_key:
            raise RuntimeError("Claude selected but no Anthropic API key configured (Settings → Model configuration).")
        self.client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
        self.cfg = cfg

    def complete(self, system, user, *, json_mode=False, tier="strong"):
        model = self.cfg.claude_model if tier == "strong" else (self.cfg.claude_fast_model or self.cfg.claude_model)
        if json_mode:
            system = system + "\n\nRespond with a single JSON object only. No prose, no markdown fences."
        msg = self.client.messages.create(
            model=model, max_tokens=4096, temperature=self.cfg.temperature, system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


_override: LLM | None = None  # used by tests to inject a fake model


def set_llm_override(llm: LLM | None) -> None:
    global _override
    _override = llm


def get_llm(cfg: LLMConfig | None = None) -> LLM:
    if _override is not None:
        return _override
    cfg = cfg or load_config()
    return ClaudeLLM(cfg) if cfg.provider == "claude" else OllamaLLM(cfg)


def parse_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not m:
            raise ValueError(f"Model did not return JSON: {raw[:300]}")
        return json.loads(m.group(0))


def test_provider(cfg: LLMConfig) -> dict:
    try:
        out = get_llm(cfg).complete("You are a health check.", "Reply with the word OK.")
        return {"ok": True, "reply": out[:50]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:300]}
