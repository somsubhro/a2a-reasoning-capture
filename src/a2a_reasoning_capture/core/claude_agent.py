"""Agent 2 backed by a real Claude model, for conversational experiments.

* A manual tool-use loop over the shared tools (lookup_fact, calculate) plus
  `ask_user`, which maps onto A2A's input-required state: Agent 2 pauses the task
  with a question, and Agent 1's reply arrives as that tool's result.
* `remember=True` keeps each conversation's full message history per contextId
  (thinking blocks included, passed back unchanged). `remember=False` starts
  from a blank history on every call: the "amnesiac".
* Every API call's usage, model, stop reason and latency is yielded as an
  `api_call` step, so the ground truth carries real token counts.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from .reasoners import TOOLS, run_tool

MODEL = os.environ.get("A2A_EXPERIMENT_MODEL", "claude-opus-5-5")
PRICE_PER_MTOK = {"claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20}}

ASK_USER = {
    "name": "ask_user",
    "description": "Ask the user a short clarifying question when a request is ambiguous. "
                   "Their reply comes back as this tool's result.",
    "input_schema": {"type": "object", "properties": {"question": {"type": "string"}},
                     "required": ["question"], "additionalProperties": False},
    "strict": True,
}

SYSTEM = """You are a Nordic population statistics agent. Another agent relays the user's requests to you.
Keep track of the user's working set of countries across the conversation.
Use lookup_fact for every population figure and calculate for every piece of arithmetic; never work numbers out yourself.
If a request is ambiguous, call ask_user with one short question instead of guessing.
Write numbers in full with comma thousands separators (e.g. 11,510,000) and percentages to one decimal place.
When the working set changes, give each country's population, the combined total and each country's share.
Keep answers to one or two sentences."""


def _step(kind: str, content: Any, **extra: Any) -> dict[str, Any]:
    return {"step_id": uuid.uuid4().hex[:12], "kind": kind, "content": content, **extra}


def cost_usd(model: str, usage: dict[str, int]) -> float:
    p = PRICE_PER_MTOK.get(model) or PRICE_PER_MTOK["claude-opus-5-5"]
    return (usage.get("input_tokens", 0) * p["input"] + usage.get("output_tokens", 0) * p["output"]
            + usage.get("cache_read_input_tokens", 0) * p["cache_read"]) / 1_000_000


class ClaudeConversationalAgent:
    def __init__(self, remember: bool = True, model: str = MODEL, client: Any = None,
                 effort: str = "medium", max_iterations: int = 10) -> None:
        if client is None:
            import anthropic
            client = anthropic.AsyncAnthropic()
        self.client, self.model, self.remember = client, model, remember
        self.effort, self.max_iterations = effort, max_iterations
        self.name = "claude" if remember else "claude-amnesiac"
        self.histories: dict[str, list[dict[str, Any]]] = {}
        self.pending: dict[str, dict[str, Any]] = {}  # context_id -> paused ask_user call

    async def run(self, context_id: str, user_text: str, task_id: str | None = None) -> AsyncIterator[dict]:
        if not self.remember:
            self.histories.pop(context_id, None)
            self.pending.pop(context_id, None)
        messages = self.histories.setdefault(context_id, [])
        paused = self.pending.pop(context_id, None)
        if paused:  # Agent 1's reply answers the question Agent 2 asked
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": paused["id"], "content": user_text}, *paused["other_results"]]})
        else:
            messages.append({"role": "user", "content": user_text})

        for _ in range(self.max_iterations):
            t0 = time.time()
            resp = await self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM,
                thinking={"type": "adaptive", "display": "summarized"},
                output_config={"effort": self.effort},
                tools=[*TOOLS, ASK_USER],
                messages=messages,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            u = resp.usage
            usage = {"input_tokens": u.input_tokens or 0, "output_tokens": u.output_tokens or 0,
                     "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
                     "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0}
            yield _step("api_call", {"model": resp.model, "stop_reason": resp.stop_reason, "usage": usage,
                                     "latency_ms": round((time.time() - t0) * 1000, 1),
                                     "cost_usd": round(cost_usd(resp.model, usage), 6)})
            if resp.stop_reason == "refusal":
                yield _step("final", f"[refused: {getattr(resp.stop_details, 'category', None)}]")
                return

            messages.append({"role": "assistant", "content": resp.content})  # unchanged, thinking included
            texts, results, ask = [], [], None
            for b in resp.content:
                if b.type == "thinking" and b.thinking:
                    yield _step("thinking", b.thinking)
                elif b.type == "text":
                    texts.append(b.text)
                    yield _step("text", b.text)
                elif b.type == "tool_use":
                    yield _step("tool_call", {"name": b.name, "input": b.input})
                    if b.name == "ask_user":
                        ask = b
                        continue
                    out = run_tool(b.name, b.input)
                    yield _step("tool_result", {"name": b.name, "output": out})
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})

            if resp.stop_reason != "tool_use":
                yield _step("final", "\n".join(texts).strip() or "(empty answer)")
                return
            if ask:  # pause the A2A task; resume when Agent 1 replies on this taskId
                self.pending[context_id] = {"id": ask.id, "other_results": results}
                yield _step("input_required", ask.input.get("question", "Could you clarify?"))
                return
            messages.append({"role": "user", "content": results})
        yield _step("final", "[stopped: iteration limit]")
