"""Agent 2 for e02: a scripted, conversational Nordic stats agent.

It keeps a working set of countries and edits it turn by turn ("add Sweden",
"remove Denmark", "which is largest?"). It supports both of Agent 1's strategies:

* stateful  : state is remembered per A2A contextId, only the new request arrives.
* stateless : no memory. The message carries the whole conversation so far, so
              Agent 2 rebuilds its state by replaying every earlier user request
              (re-using population figures it finds in the earlier answers
              instead of looking them up again).

Every step is logged as ground truth, so we can count the extra work.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any

from ...core.reasoners import run_tool

COUNTRIES = ["norway", "denmark", "sweden", "finland", "iceland"]
FIGURE_RE = re.compile(r"\b(Norway|Denmark|Sweden|Finland|Iceland) ([\d,]{5,})\b")

HISTORY_HEADER = "[Conversation so far]"
CURRENT_HEADER = "[Current request]"


def envelope(history: list[tuple[str, str]], current: str) -> str:
    """How Agent 1 packs the conversation for a stateless call."""
    lines = [HISTORY_HEADER] + [f"{who}: {text}" for who, text in history] + ["", CURRENT_HEADER, current]
    return "\n".join(lines)


def _step(kind: str, content: Any, **extra: Any) -> dict[str, Any]:
    return {"step_id": uuid.uuid4().hex[:12], "kind": kind, "content": content, **extra}


def _fmt(n: float) -> str:
    return f"{int(round(n)):,}"


@dataclass
class State:
    countries: list[str] = field(default_factory=list)
    pop: dict[str, int] = field(default_factory=dict)
    totals: list[int] = field(default_factory=list)
    pending: bool = False  # waiting for the user to say which country


def _named(t: str) -> list[str]:
    return sorted((c for c in COUNTRIES if re.search(rf"\b{c}\b", t)), key=t.index)


class ConversationalStatsAgent:
    name = "scripted-conversational"

    def __init__(self) -> None:
        self.memory: dict[str, State] = {}

    async def run(self, context_id: str, user_text: str, task_id: str | None = None) -> AsyncIterator[dict]:
        if user_text.startswith(HISTORY_HEADER):
            # Stateless: rebuild everything from the pasted history.
            head, _, current = user_text.partition(f"\n\n{CURRENT_HEADER}\n")
            lines = head.splitlines()[1:]
            figures = {m.group(1).lower(): int(m.group(2).replace(",", ""))
                       for line in lines if line.startswith("Agent 1: ") for m in FIGURE_RE.finditer(line)}
            user_lines = [line[len("User: "):] for line in lines if line.startswith("User: ")]
            yield _step("thinking", f"No memory for this context. Rebuilding state from {len(lines)} lines of "
                                    f"pasted history ({len(user_lines)} earlier user requests).")
            state = State()
            for i, line in enumerate(user_lines, 1):
                changed = False
                for s in self._apply(state, line, figures, replay=True):
                    changed = True
                    yield s
                yield _step("replay", {"request": i, "text": line, "changed_state": changed})
            text = current
        else:
            state = self.memory.setdefault(context_id, State())
            figures = {}
            text = user_text
        for s in self._apply(state, text, figures, replay=False):
            yield s

    # ------------------------------------------------------------------ logic

    def _ensure_pop(self, state: State, figures: dict[str, int], replay: bool) -> Iterator[dict]:
        for c in state.countries:
            if c in state.pop:
                continue
            if c in figures:
                state.pop[c] = figures[c]
                yield _step("figure_reused", {"country": c, "from": "history"}, replay=replay)
                continue
            args = {"query": f"population of {c}"}
            yield _step("tool_call", {"name": "lookup_fact", "input": args}, replay=replay)
            out = run_tool("lookup_fact", args)
            state.pop[c] = int(out.split(" ")[0].replace(",", ""))
            yield _step("tool_result", {"name": "lookup_fact", "output": out}, replay=replay)

    def _total(self, state: State, replay: bool) -> Iterator[dict]:
        expr = " + ".join(str(state.pop[c]) for c in state.countries)
        if replay:  # re-deriving an earlier total: no tool call, but it is still work
            total = sum(state.pop[c] for c in state.countries)
            yield _step("thinking", f"(replay) earlier total was {_fmt(total)}", replay=True)
        else:
            yield _step("tool_call", {"name": "calculate", "input": {"expression": expr}})
            total = int(float(run_tool("calculate", {"expression": expr})))
            yield _step("tool_result", {"name": "calculate", "output": str(total)})
        state.totals.append(total)

    def _summary(self, state: State) -> str:
        total = state.totals[-1]
        pops = "; ".join(f"{c.title()} {_fmt(state.pop[c])}" for c in state.countries)
        shares = ", ".join(f"{c.title()} {100 * state.pop[c] / total:.1f}%" for c in state.countries)
        return f"{pops}. Combined: {_fmt(total)}. Shares: {shares}."

    def _apply(self, state: State, text: str, figures: dict[str, int], replay: bool) -> Iterator[dict]:
        t = text.lower().strip()
        named = _named(t)
        has = lambda *words: any(re.search(rf"\b{w}\b", t) for w in words)  # noqa: E731

        # A bare country name answers an earlier clarifying question.
        if state.pending and named and not has("add", "remove", "drop", "share", "list"):
            state.pending = False
            state.countries += [c for c in named if c not in state.countries]
            yield from self._ensure_pop(state, figures, replay)
            yield from self._total(state, replay)
            if not replay:
                yield _step("final", self._summary(state))
            return

        if has("add") and "remaining" in t:
            remaining = [c.title() for c in COUNTRIES if c not in state.countries]
            state.pending = True
            if not replay:
                yield _step("thinking", f"'The remaining Nordic country' is ambiguous: {remaining} are all missing.")
                yield _step("input_required",
                            f"Which country do you mean: {', '.join(remaining[:-1])} or {remaining[-1]}?")
            return

        if replay and not (has("combined", "add", "remove", "drop") or "start over" in t):
            return  # questions don't change state; nothing to rebuild

        if has("compare") and "first" in t:
            first, now = state.totals[0], state.totals[-1]
            yield _step("thinking", f"First total {first}, current {now}.")
            yield _step("final", f"Now {_fmt(now)} vs your first total {_fmt(first)}: "
                                 f"{_fmt(abs(now - first))} {'more' if now >= first else 'less'}.")
            return

        if "same as" in t and has("earlier"):
            now, earlier = state.totals[-1], state.totals[:-1]
            match = now in earlier
            yield _step("thinking", f"Current total {now}; earlier totals {earlier}.")
            yield _step("final", f"Yes: {_fmt(now)} matches an earlier total." if match
                        else f"No: {_fmt(now)} doesn't match any earlier total.")
            return

        if has("largest", "smallest"):
            pick = (max if has("largest") else min)(state.countries, key=state.pop.__getitem__)
            word = "largest" if has("largest") else "smallest"
            yield _step("thinking", f"Comparing {state.countries} by population.")
            yield _step("final", f"Of {', '.join(c.title() for c in state.countries)}, the {word} is "
                                 f"{pick.title()} ({_fmt(state.pop[pick])}).")
            return

        if has("share") and named:
            c, total = named[0], state.totals[-1]
            yield _step("final", f"{c.title()} is {100 * state.pop[c] / total:.1f}% of the combined {_fmt(total)}.")
            return

        if has("list"):
            yield _step("final", "; ".join(f"{c.title()} {_fmt(state.pop[c])}" for c in state.countries) + ".")
            return

        if has("combined") or "start over" in t:
            state.countries = list(named)
        elif has("remove", "drop", "add") and named:
            add_at = re.search(r"\badd\b", t)
            before = t[: add_at.start()] if add_at else t
            after = t[add_at.start():] if add_at else ""
            if has("remove", "drop"):
                drop = _named(before)
                state.countries = [c for c in state.countries if c not in drop]
            state.countries += [c for c in _named(after) if c not in state.countries]
        else:
            if not replay:
                yield _step("final", "I can only help with population figures for Nordic countries.")
            return

        if not replay:
            yield _step("thinking", f"Working set is now {state.countries}.")
        yield from self._ensure_pop(state, figures, replay)
        yield from self._total(state, replay)
        if not replay:
            yield _step("final", self._summary(state))
