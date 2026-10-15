"""Embeddings for pgvector RAG.

Both LLM modes embed with Ollama (`nomic-embed-text`, 768-d) because it is free and local — Claude has no
embedding endpoint. If Ollama is unreachable we fall back to a deterministic hashed bag-of-words vector so the
platform still works in dev (lower retrieval quality; a warning is logged)."""
from __future__ import annotations

import hashlib
import logging
import math
import re

import httpx

from ..config import get_settings
from .providers import load_config

log = logging.getLogger(__name__)
_warned = False
_force_fallback = False


def use_fallback(flag: bool = True) -> None:
    global _force_fallback
    _force_fallback = flag


def _hash_embed(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    grams = tokens + [a + "_" + b for a, b in zip(tokens, tokens[1:])]
    for tok in grams:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0 if (h >> 8) & 1 else -1.0
        # split snake_case identifiers so "invoice_date" matches "invoice" and "date"
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed(texts: list[str]) -> list[list[float]]:
    global _warned
    dim = get_settings().embedding_dim
    texts = [t.replace("_", " ") + " " + t for t in texts]
    if not _force_fallback:
        cfg = load_config()
        try:
            r = httpx.post(f"{cfg.ollama_url.rstrip('/')}/api/embed",
                           json={"model": cfg.ollama_embed_model, "input": texts}, timeout=120)
            r.raise_for_status()
            vecs = r.json()["embeddings"]
            if vecs and len(vecs[0]) == dim:
                return vecs
            log.warning("Embedding dim %s != configured %s; using fallback", len(vecs[0]) if vecs else 0, dim)
        except Exception as e:  # noqa: BLE001
            if not _warned:
                log.warning("Ollama embeddings unavailable (%s) — using hashed fallback embeddings", e)
                _warned = True
    return [_hash_embed(t, dim) for t in texts]
