"""The OpenAI-compatible chat API that llama-server (or vLLM) serves.

BOOKGRAPH_LLM sets the base URL, by default http://127.0.0.1:8080, which is
where host/install.sh puts llama-server; reach a remote one through
ssh -L 8080:127.0.0.1:8080. Each call asks for JSON matching a pydantic
model and validates the answer here; a bad answer is retried.

BOOKGRAPH_GRAMMAR picks what llama-server enforces while it generates:
"json" (default) only valid JSON syntax, with the schema in the system
prompt; "schema" the full schema as a grammar. On the A100 with Qwen3.8 the
full grammar cost about 30% of generation speed at 8 parallel requests,
and plain JSON mode costs nothing measurable.

Every call names one of SETTINGS, the sampling for its kind of work (see
PLAN.md, "Model settings"). BOOKGRAPH_MODEL names the served model to ask
for; without it the server's only model answers, and Client.model() asks
the server which one that is.
"""

import asyncio
import json
import os
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

BASE = os.environ.get("BOOKGRAPH_LLM", "http://127.0.0.1:8080").rstrip("/")
GRAMMAR = os.environ.get("BOOKGRAPH_GRAMMAR", "json")
MODEL = os.environ.get("BOOKGRAPH_MODEL", "")
RETRIES = 3
SEED = 20261006
T = TypeVar("T", bound=BaseModel)

# Thinking calls are never greedy: Qwen loops at low temperature.
SETTINGS = {
    "extract": {"temperature": 0.2, "top_p": 0.8, "top_k": 20, "think": False},
    "merge": {"temperature": 0.15, "top_p": 0.8, "top_k": 20, "think": False},
    "think": {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "think": True},
    "compare": {"temperature": 0.3, "top_p": 0.8, "top_k": 20, "think": False},
    "notes": {"temperature": 0.5, "top_p": 0.9, "top_k": 20, "think": False},
    # The silver-set judge (gold silver): a bigger model, thinking.
    "judge": {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "think": True},
}


class Stats:
    def __init__(self) -> None:
        self.prompt = 0
        self.completion = 0
        self.start = time.monotonic()

    def line(self) -> str:
        s = max(time.monotonic() - self.start, 1e-9)
        return (f"{self.prompt} prompt + {self.completion} generated tokens in {s:.0f}s "
                f"({self.completion / s:.1f} gen tok/s overall)")


class Client:
    def __init__(self, concurrency: int, timeout: float = 1800) -> None:
        self.http = httpx.AsyncClient(base_url=BASE, timeout=timeout)
        self.limit = asyncio.Semaphore(concurrency)
        self.stats = Stats()
        self._model = MODEL

    async def model(self) -> str:
        if not self._model:
            r = await self.http.get("/v1/models")
            r.raise_for_status()
            self._model = r.json()["data"][0]["id"]
        return self._model

    async def close(self) -> None:
        await self.http.aclose()

    async def tokenize(self, text: str) -> int:
        r = await self.http.post("/tokenize", json={"content": text})
        r.raise_for_status()
        return len(r.json()["tokens"])

    async def ask(self, model: type[T], system: str, user: str, *,
                  kind: str, max_tokens: int = 4096) -> T:
        body = request(model, system, user, kind=kind, max_tokens=max_tokens)
        if self._model:
            body["model"] = self._model
        error = None
        last = ""
        for attempt in range(RETRIES):
            async with self.limit:
                r = await self.http.post("/v1/chat/completions", json=body)
            if r.is_error:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
            data = r.json()
            usage = data.get("usage", {})
            self.stats.prompt += usage.get("prompt_tokens", 0)
            self.stats.completion += usage.get("completion_tokens", 0)
            choice = data["choices"][0]
            content = last = choice["message"].get("content") or ""
            # Without a reasoning parser on the server, the thinking comes
            # back inside the content.
            content = content.rsplit("</think>", 1)[-1].strip()
            try:
                return model.model_validate_json(content)
            except ValidationError as e:
                error = e
                reason = choice.get("finish_reason")
                print(f"  retry {attempt + 1}: invalid JSON (finish_reason={reason}): "
                      f"{str(e).splitlines()[0]}")
                if reason == "length":
                    body["max_tokens"] = int(body["max_tokens"] * 1.5)
        # The last answer shows whether the model refused or just broke the JSON.
        raise RuntimeError(f"no valid answer after {RETRIES} tries; last: {last[:400]!r}") from error


def request(model: type[BaseModel], system: str, user: str, *,
            kind: str, max_tokens: int) -> dict:
    """The chat request body for one call of the given kind of work."""
    opts = SETTINGS[kind]
    schema = model.model_json_schema()
    if GRAMMAR == "schema":
        fmt = {"type": "json_schema", "json_schema": {"name": model.__name__, "schema": schema}}
    else:
        fmt = {"type": "json_object"}
        system += ("\n\nJSON Schema ответа (соблюдай имена полей и типы точно):\n"
                   + json.dumps(schema, ensure_ascii=False, separators=(",", ":")))
    return {
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": opts["temperature"],
        "top_p": opts["top_p"],
        "top_k": opts["top_k"],
        "seed": SEED,
        "max_tokens": max_tokens,
        "response_format": fmt,
        # Qwen's and GLM's chat templates read enable_thinking, DeepSeek-V4's
        # thinking and reasoning_effort; each ignores the others' keys.
        "chat_template_kwargs": {"enable_thinking": opts["think"], "thinking": opts["think"],
                                 **({"reasoning_effort": "high"} if opts["think"] else {})},
    }


def dump(model: BaseModel) -> dict:
    return json.loads(model.model_dump_json())
