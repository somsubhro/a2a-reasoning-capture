"""Shared Agent 2 tools and reasoning loops (scripted and Claude).

A reasoner yields Step dicts as it works. Every step is also the *ground truth*
the experiment later tries to recover on Agent 1's side of the A2A wire.

Step kinds: thinking | text | tool_call | tool_result | final
"""

from __future__ import annotations

import ast
import json
import operator
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

# ---------------------------------------------------------------------------
# Tools available to Agent 2 (deterministic, local)
# ---------------------------------------------------------------------------

FACTS = {
    "population of norway": "5,550,000 (2024 estimate)",
    "population of denmark": "5,960,000 (2024 estimate)",
    "population of sweden": "10,550,000 (2024 estimate)",
    "population of finland": "5,600,000 (2024 estimate)",
    "population of iceland": "390,000 (2024 estimate)",
}

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.USub: operator.neg}


def _safe_eval(expr: str) -> float:
    def ev(n: ast.AST) -> float:
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        raise ValueError(f"unsupported expression: {expr}")
    return ev(ast.parse(expr.replace(",", ""), mode="eval"))


def run_tool(name: str, args: dict[str, Any]) -> str:
    if name == "lookup_fact":
        return FACTS.get(args.get("query", "").strip().lower(), "no fact found")
    if name == "calculate":
        try:
            return str(round(_safe_eval(args["expression"]), 4))
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"
    return f"error: unknown tool {name}"


TOOLS = [
    {
        "name": "lookup_fact",
        "description": "Look up a fact. Supported queries look like 'population of <country>' "
                       "for Norway, Denmark, Sweden, Finland, Iceland.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}},
                         "required": ["query"], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "calculate",
        "description": "Evaluate an arithmetic expression with + - * / and parentheses.",
        "input_schema": {"type": "object", "properties": {"expression": {"type": "string"}},
                         "required": ["expression"], "additionalProperties": False},
        "strict": True,
    },
]


def _step(kind: str, content: Any, **extra: Any) -> dict[str, Any]:
    return {"step_id": uuid.uuid4().hex[:12], "kind": kind, "content": content, **extra}


# ---------------------------------------------------------------------------
# Scripted reasoner: deterministic, no API key needed
# ---------------------------------------------------------------------------

class ScriptedReasoner:
    """Replays a fixed think -> tool -> think -> answer loop.

    Keeps per-contextId memory so turn 2 can only be answered correctly if the
    agent remembers turn 1 (tests multi-turn retention on Agent 2's side).
    """

    name = "scripted"

    def __init__(self) -> None:
        self.memory: dict[str, dict[str, Any]] = {}

    async def run(self, context_id: str, user_text: str, task_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        mem = self.memory.setdefault(context_id, {"turns": 0, "known": {}})
        mem["turns"] += 1
        text = user_text.lower()
        wanted = [c for c in ("norway", "denmark", "sweden", "finland") if c in text]
        remembered = [c for c in mem["known"] if c not in wanted]

        yield _step("thinking", f"Turn {mem['turns']} in context. User asks about {wanted or 'nothing new'}. "
                                f"I remember from earlier turns: {remembered or 'nothing'}. "
                                "Plan: look up each missing population, then compute the total and shares.")
        for c in wanted:
            args = {"query": f"population of {c}"}
            yield _step("tool_call", {"name": "lookup_fact", "input": args})
            result = run_tool("lookup_fact", args)
            mem["known"][c] = int(result.split(" ")[0].replace(",", ""))
            yield _step("tool_result", {"name": "lookup_fact", "output": result})

        countries = list(mem["known"])
        yield _step("thinking", f"I now have populations for {countries}. "
                                "Summing them and computing each country's percentage share.")
        expr = " + ".join(str(mem["known"][c]) for c in countries)
        yield _step("tool_call", {"name": "calculate", "input": {"expression": expr}})
        total = run_tool("calculate", {"expression": expr})
        yield _step("tool_result", {"name": "calculate", "output": total})
        shares = ", ".join(f"{c.title()} {100 * mem['known'][c] / float(total):.1f}%" for c in countries)
        yield _step("text", "Checked the numbers; writing the answer.")
        yield _step("final", f"Combined population of {', '.join(c.title() for c in countries)}: "
                             f"{int(float(total)):,}. Shares: {shares}.")


# ---------------------------------------------------------------------------
# Claude reasoner: real Opus 5.5 tool loop with summarized thinking
# ---------------------------------------------------------------------------

class ClaudeReasoner:
    """Manual tool-use loop on Claude Opus 5.5.

    Note: the API never returns raw chain of thought; with display="summarized"
    thinking blocks carry a readable *summary*. That summary is the most
    reasoning Agent 2 itself can see, so it is the ceiling for capture via A2A.
    """

    name = "claude"
    model = os.environ.get("A2A_EXPERIMENT_MODEL", "claude-opus-5-5")

    def __init__(self) -> None:
        import anthropic
        self.client = anthropic.AsyncAnthropic()
        self.histories: dict[str, list[dict[str, Any]]] = {}

    async def run(self, context_id: str, user_text: str, task_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        messages = self.histories.setdefault(context_id, [])
        messages.append({"role": "user", "content": user_text})
        system = ("You are a research agent. Use the tools for every fact and every calculation; "
                  "never compute in your head. Finish with a short answer.")
        for _ in range(12):
            resp = await self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system,
                thinking={"type": "adaptive", "display": "summarized"},
                output_config={"effort": "medium"},
                tools=TOOLS,
                messages=messages,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            if resp.stop_reason == "refusal":
                yield _step("final", f"[refused: {getattr(resp.stop_details, 'category', None)}]")
                return
            # keep the assistant turn unchanged (thinking blocks must round-trip)
            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for b in resp.content:
                if b.type == "thinking":
                    if b.thinking:
                        yield _step("thinking", b.thinking)
                elif b.type == "text":
                    yield _step("final" if resp.stop_reason == "end_turn" else "text", b.text)
                elif b.type == "tool_use":
                    yield _step("tool_call", {"name": b.name, "input": b.input})
                    out = run_tool(b.name, b.input)
                    yield _step("tool_result", {"name": b.name, "output": out})
                    tool_results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
            if resp.stop_reason != "tool_use":
                return
            messages.append({"role": "user", "content": tool_results})
        yield _step("final", "[stopped: iteration limit]")


def make_reasoner(kind: str):
    return ClaudeReasoner() if kind == "claude" else ScriptedReasoner()


def step_text(step: dict[str, Any]) -> str:
    """Canonical text of a step, used to look for it on the client side."""
    c = step["content"]
    return c if isinstance(c, str) else json.dumps(c, sort_keys=True)
