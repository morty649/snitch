"""LLM client. Talks to ANY OpenAI-compatible endpoint (Together, Fireworks, OpenRouter, Groq,
Meta Llama API, vLLM, Ollama...). Configured only through environment variables:

    SNITCH_BASE_URL   e.g. https://api.together.xyz/v1
    SNITCH_API_KEY    the key
    SNITCH_MODEL      e.g. Qwen/Qwen2.5-Coder-32B-Instruct

FakeLLM returns canned answers so tests never touch the network.
"""
from __future__ import annotations

import json
import os
import re
from typing import Callable, Protocol


class LLM(Protocol):
    name: str

    def complete(self, system: str, user: str, temperature: float = 0.7) -> str: ...


class OpenAICompatLLM:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        from openai import OpenAI  # imported lazily so tests don't need network config

        self.base_url = base_url or os.environ.get("SNITCH_BASE_URL")
        # falls back to OPENROUTER_API_KEY (e.g. exported in ~/.zshrc) so the key never has to live in .env
        self.api_key = api_key or os.environ.get("SNITCH_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
        self.name = model or os.environ.get("SNITCH_MODEL", "")
        missing = [k for k, v in {"SNITCH_BASE_URL": self.base_url, "SNITCH_API_KEY": self.api_key, "SNITCH_MODEL": self.name}.items() if not v]
        if missing:
            raise RuntimeError(f"Missing env vars: {', '.join(missing)} (the key can also come from OPENROUTER_API_KEY). See README 'Configure a model'.")
        self._client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=120)

    def complete(self, system: str, user: str, temperature: float = 0.7) -> str:
        """Returns the reply text. Retries twice on API errors, then raises."""
        import time
        last: Exception | None = None
        for attempt in range(3):
            try:
                resp = self._client.chat.completions.create(
                    model=self.name,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    temperature=temperature,
                    max_tokens=4000,
                )
                # OpenRouter free models sometimes return HTTP 200 with an error and no choices
                if not getattr(resp, "choices", None) or not resp.choices[0].message.content:
                    raise RuntimeError(f"empty/error response: {getattr(resp, 'error', None) or 'no content'}")
                break
            except Exception as e:  # network, rate limit, 5xx
                last = e
                time.sleep(2 * (attempt + 1))
        else:
            raise RuntimeError(f"LLM call failed after 3 attempts: {last}")
        text = resp.choices[0].message.content or ""
        _debug_dump(system, user, text)
        return text


def _debug_dump(system: str, user: str, reply: str) -> None:
    """If SNITCH_DEBUG_DIR is set, save every prompt+reply as a numbered .txt file for debugging."""
    d = os.environ.get("SNITCH_DEBUG_DIR")
    if not d:
        return
    from pathlib import Path
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    n = len(list(p.glob("call_*.txt")))
    (p / f"call_{n:04d}.txt").write_text(f"=== SYSTEM ===\n{system}\n\n=== USER ===\n{user}\n\n=== REPLY ===\n{reply}\n", encoding="utf-8")


def load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (KEY=VALUE lines). Does not override variables already set."""
    from pathlib import Path
    f = Path(path)
    if not f.is_file():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class FakeLLM:
    """Deterministic stand-in for tests. `responder(system, user) -> str`."""

    def __init__(self, responder: Callable[[str, str], str], name: str = "fake"):
        self.responder = responder
        self.name = name
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, temperature: float = 0.7) -> str:
        self.calls.append((system, user))
        return self.responder(system, user)


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str):
    """Pull the first JSON object/array out of a model reply (handles ```json fences and chatter).

    Raises ValueError if nothing parses.
    """
    candidates = [m.group(1) for m in _FENCE_RE.finditer(text)] + [text]
    for c in candidates:
        c = c.strip()
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            pass
        # fall back: outermost [...] or {...}, whichever opens first
        pairs = sorted((("[", "]"), ("{", "}")), key=lambda p: (c.find(p[0]) == -1, c.find(p[0])))
        for open_ch, close_ch in pairs:
            s, e = c.find(open_ch), c.rfind(close_ch)
            if s != -1 and e > s:
                try:
                    return json.loads(c[s : e + 1])
                except json.JSONDecodeError:
                    continue
    raise ValueError(f"No JSON found in model output: {text[:200]!r}")
