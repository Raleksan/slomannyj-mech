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
RETRIES = 3
T = TypeVar("T", bound=BaseModel)


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

    async def close(self) -> None:
        await self.http.aclose()

    async def tokenize(self, text: str) -> int:
        r = await self.http.post("/tokenize", json={"content": text})
        r.raise_for_status()
        return len(r.json()["tokens"])

    async def ask(self, model: type[T], system: str, user: str, *,
                  think: bool = False, max_tokens: int = 4096,
                  temperature: float = 0.3) -> T:
        schema = model.model_json_schema()
        if GRAMMAR == "schema":
            fmt = {"type": "json_schema", "json_schema": {"name": model.__name__, "schema": schema}}
        else:
            fmt = {"type": "json_object"}
            system += ("\n\nJSON Schema ответа (соблюдай имена полей и типы точно):\n"
                       + json.dumps(schema, ensure_ascii=False, separators=(",", ":")))
        body = {
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": temperature,
            "top_p": 0.9,
            "max_tokens": max_tokens,
            "response_format": fmt,
            # Qwen's chat template reads this; other templates ignore it.
            "chat_template_kwargs": {"enable_thinking": think},
        }
        error = None
        for attempt in range(RETRIES):
            async with self.limit:
                r = await self.http.post("/v1/chat/completions", json=body)
            r.raise_for_status()
            data = r.json()
            usage = data.get("usage", {})
            self.stats.prompt += usage.get("prompt_tokens", 0)
            self.stats.completion += usage.get("completion_tokens", 0)
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            try:
                return model.model_validate_json(content)
            except ValidationError as e:
                error = e
                reason = choice.get("finish_reason")
                print(f"  retry {attempt + 1}: invalid JSON (finish_reason={reason}): "
                      f"{str(e).splitlines()[0]}")
                if reason == "length":
                    body["max_tokens"] = int(body["max_tokens"] * 1.5)
        raise RuntimeError(f"no valid answer after {RETRIES} tries") from error


def dump(model: BaseModel) -> dict:
    return json.loads(model.model_dump_json())
