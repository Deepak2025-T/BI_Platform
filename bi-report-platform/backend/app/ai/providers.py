"""
Talks to the AI providers. Every call asks for a JSON answer that matches a schema.

- ollama: a local Ollama server (https://ollama.com), e.g. http://localhost:11434
- anthropic: the Claude API, through the official anthropic SDK
- openai_compatible: any server with the /v1/chat/completions API, e.g. LM Studio, vLLM,
  llama.cpp server, LocalAI, or a hosted service
"""

import json
import re
import time
from dataclasses import dataclass

import anthropic
import httpx

from ..config import settings

PROVIDERS = {
    "ollama": {"label": "Ollama", "needs_base_url": True, "needs_key": False,
               "default_base_url": "http://localhost:11434"},
    "anthropic": {"label": "Claude (Anthropic API)", "needs_base_url": False, "needs_key": True,
                  "default_base_url": ""},
    "openai_compatible": {"label": "OpenAI-compatible server", "needs_base_url": True, "needs_key": False,
                          "default_base_url": "http://localhost:1234/v1"},
}

# Current Claude models, offered as choices on the form.
CLAUDE_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"]
# Models that take the server-side refusal fallback ("default" routes by refusal category).
_CLAUDE_FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
# Models where a low effort setting is accepted; it keeps simple questions fast and cheap.
_CLAUDE_EFFORT_MODELS = _CLAUDE_FALLBACK_MODELS | {"claude-haiku-5-5", "claude-sonnet-5", "claude-fable-5"}

# How long to wait for an answer. A large local model (e.g. a 27B at Q4_K_M) on a CPU can
# need several minutes for the first call, because the weights are loaded into memory first.
# Raise AI_TIMEOUT_SECONDS in backend/.env if a model is still cut off.
TIMEOUT = float(settings.ai_timeout_seconds)

# Connecting is fast even when answering isn't, so a refused connection is reported straight away.
HTTP_TIMEOUT = httpx.Timeout(TIMEOUT, connect=10.0)

# Keeps a local Ollama model in memory between calls, so only the first call pays the load time.
OLLAMA_KEEP_ALIVE = settings.ollama_keep_alive


class AIError(Exception):
    """The model couldn't be reached or didn't give a usable answer. The message is safe to show."""


@dataclass
class ModelSpec:
    provider: str
    model: str
    base_url: str = ""
    api_key: str = ""


def _base(url: str) -> str:
    return url.strip().rstrip("/")


def _parse_json(text: str) -> dict:
    """Reads the JSON object from a reply, allowing for code fences or extra words around it."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise AIError("The model's answer wasn't valid JSON. Try a larger or more capable model.")


def complete_json(spec: ModelSpec, system: str, user: str, schema: dict) -> dict:
    """Asks the model one question and returns its JSON answer."""
    if spec.provider == "anthropic":
        return _claude(spec, system, user, schema)
    if spec.provider == "ollama":
        return _ollama(spec, system, user, schema)
    if spec.provider == "openai_compatible":
        return _openai_compatible(spec, system, user, schema)
    raise AIError(f"Unknown provider: {spec.provider}")


def ping(spec: ModelSpec) -> tuple[int, str]:
    """A tiny request to check the model answers. Returns (milliseconds, reply)."""
    t0 = time.perf_counter()
    answer = complete_json(spec, "You are a connectivity check. Answer in JSON only.",
                           'Reply with {"reply": "OK"}.',
                           {"type": "object", "properties": {"reply": {"type": "string"}},
                            "required": ["reply"], "additionalProperties": False})
    return round((time.perf_counter() - t0) * 1000), str(answer.get("reply", ""))[:60]


def discover(provider: str, base_url: str, api_key: str) -> list[str]:
    """The model ids available on the server, for the form's model list."""
    try:
        if provider == "ollama":
            res = httpx.get(f"{_base(base_url)}/api/tags", timeout=10)
            res.raise_for_status()
            return sorted(m["name"] for m in res.json().get("models", []))
        if provider == "openai_compatible":
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            res = httpx.get(f"{_base(base_url)}/models", headers=headers, timeout=10)
            res.raise_for_status()
            return sorted(m["id"] for m in res.json().get("data", []))
        if provider == "anthropic":
            client = anthropic.Anthropic(api_key=api_key, timeout=10, max_retries=1)
            return [m.id for m in client.models.list()]
    except anthropic.AuthenticationError:
        raise AIError("The API key was rejected.")
    except (anthropic.APIError, httpx.HTTPError, KeyError, ValueError) as err:
        raise AIError(_http_message(err))
    raise AIError(f"Unknown provider: {provider}")


# ---------- Claude (official SDK) ----------

def _claude(spec: ModelSpec, system: str, user: str, schema: dict) -> dict:
    if not spec.api_key:
        raise AIError("No API key is saved for this model.")
    client = anthropic.Anthropic(api_key=spec.api_key, timeout=TIMEOUT, max_retries=1)
    output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
    if spec.model in _CLAUDE_EFFORT_MODELS:
        output_config["effort"] = "low"
    request = {"model": spec.model, "max_tokens": 4000, "system": system,
               "messages": [{"role": "user", "content": user}], "output_config": output_config}
    try:
        if spec.model in _CLAUDE_FALLBACK_MODELS:
            # If a safety classifier declines, the API retries on a fallback model in the same call.
            response = client.beta.messages.create(**request, betas=["server-side-fallback-2026-07-01"],
                                                   fallbacks="default")
        else:
            response = client.messages.create(**request)
    except anthropic.AuthenticationError:
        raise AIError("The Claude API key was rejected.")
    except anthropic.NotFoundError:
        raise AIError(f'The Claude API doesn\'t know the model "{spec.model}".')
    except anthropic.RateLimitError:
        raise AIError("The Claude API rate limit was reached. Try again in a minute.")
    except anthropic.APIStatusError as err:
        raise AIError(f"The Claude API returned an error ({err.status_code}): {err.message}"[:300])
    except anthropic.APIConnectionError:
        raise AIError("Couldn't reach the Claude API. Check the server's internet connection.")
    if response.stop_reason == "refusal":
        raise AIError("Claude declined to answer this question.")
    text = next((b.text for b in response.content if b.type == "text"), "")
    return _parse_json(text)


# ---------- Ollama ----------

def _with_schema(system: str, schema: dict) -> str:
    return f"{system}\n\nAnswer with one JSON object matching this JSON schema, and nothing else:\n{json.dumps(schema)}"


def _ollama(spec: ModelSpec, system: str, user: str, schema: dict) -> dict:
    # Local models are held to the schema by "format"; Ollama's cloud models ignore it, so the
    # schema also goes in the prompt.
    system = _with_schema(system, schema)
    body = {"model": spec.model, "stream": False, "format": schema, "options": {"temperature": 0},
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    try:
        res = httpx.post(f"{_base(spec.base_url)}/api/chat", json=body, timeout=HTTP_TIMEOUT)
        if res.status_code == 404:
            raise AIError(f'Ollama doesn\'t have the model "{spec.model}". Run: ollama pull {spec.model}')
        res.raise_for_status()
        return _parse_json(res.json()["message"]["content"])
    except AIError:
        raise
    except (httpx.HTTPError, KeyError, ValueError) as err:
        raise AIError(_http_message(err, "Is Ollama running?"))


# ---------- OpenAI-compatible ----------

def _openai_compatible(spec: ModelSpec, system: str, user: str, schema: dict) -> dict:
    # Servers differ in which response_format options they support, so the schema goes in the prompt.
    system = _with_schema(system, schema)
    body = {"model": spec.model, "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    headers = {"Authorization": f"Bearer {spec.api_key}"} if spec.api_key else {}
    try:
        res = httpx.post(f"{_base(spec.base_url)}/chat/completions", json=body, headers=headers,
                         timeout=HTTP_TIMEOUT)
        if res.status_code in (401, 403):
            raise AIError("The server rejected the API key.")
        res.raise_for_status()
        return _parse_json(res.json()["choices"][0]["message"]["content"] or "")
    except AIError:
        raise
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as err:
        raise AIError(_http_message(err, "Is the server running, and does the address end in /v1?"))


def _http_message(err: Exception, hint: str = "") -> str:
    if isinstance(err, httpx.ConnectError):
        return f"Couldn't connect to the server. {hint}".strip()
    if isinstance(err, httpx.TimeoutException):
        return (f"The model took longer than {int(TIMEOUT)}s to answer. A large model loading on a CPU "
                "can need several minutes: raise AI_TIMEOUT_SECONDS in backend/.env, or use a smaller model.")
    if isinstance(err, httpx.HTTPStatusError):
        detail = err.response.text
        try:  # Ollama and OpenAI-style servers put the reason in "error" (a string or {"message": ...})
            body = err.response.json()
            detail = body.get("error", detail) if isinstance(body, dict) else detail
            detail = detail.get("message", detail) if isinstance(detail, dict) else detail
        except ValueError:
            pass
        return f"The server returned an error ({err.response.status_code}): {str(detail)[:250]}"
    return (str(err) or type(err).__name__)[:300]
