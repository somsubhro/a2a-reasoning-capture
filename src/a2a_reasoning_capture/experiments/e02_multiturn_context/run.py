"""e02 · Multi-turn context through an entry-point agent.

The user only talks to Agent 1. Agent 1 delegates some turns to Agent 2 over A2A.
The same 17-turn conversation is run once per context strategy:

* stateful  : Agent 1 reuses Agent 2's contextId and sends only the new request
              (and resumes an input-required task with its taskId).
* stateless : Agent 1 starts a new context every call and pastes the whole
              user <-> Agent 1 conversation so far into the message.

    uv run a2a-exp e02
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
from a2a.client import ClientConfig, create_client
from a2a.types.a2a_pb2 import GetTaskRequest, Message, Part, Role, SendMessageRequest

from ...core.recording import TeeTransport, append_jsonl, new_run_dir, read_jsonl, serve, to_dict
from ...core.remote_agent import build_app
from .agent2 import ConversationalStatsAgent, envelope
from .scenario import TURNS

EXPERIMENT_ID = "e02_multiturn_context"
QUESTION = ("If the user only talks to Agent 1, how efficient is a multi-turn conversation when Agent 1 "
            "relies on Agent 2's memory (contextId) versus resending the history itself?")
STRATEGIES = ["stateful", "stateless"]


# --------------------------------------------------------------------------- Agent 1

class EntryAgent:
    """Agent 1: the only agent the user talks to. Scripted routing."""

    def __init__(self, client, transport: TeeTransport, strategy: str, out: Path) -> None:
        self.client, self.transport, self.strategy, self.out = client, transport, strategy, out
        self.history: list[tuple[str, str]] = []  # the user <-> Agent 1 conversation
        self.context_id: str | None = None
        self.pending_task: str | None = None      # an Agent 2 task waiting for the user's input
        self.task_ids: list[str] = []
        self.context_ids: list[str] = []

    async def handle(self, n: int, turn: dict) -> dict[str, Any]:
        rec: dict[str, Any] = {"turn": n, "user": turn["text"], "route": turn["route"]}
        if turn["route"] == "self" and not self.pending_task:
            reply = turn["self_reply"]
            rec.update(a2a_calls=0, chars_sent=0, bytes_out=0, bytes_in=0, latency_ms=0.0, state="-")
        else:
            reply, info = await self._ask_agent2(n, turn["text"])
            rec.update(a2a_calls=1, **info)
        self.history += [("User", turn["text"]), ("Agent 1", reply)]
        rec["reply"] = reply
        if "expect" in turn:
            rec["correct"] = turn["expect"] in reply
        return rec

    async def _ask_agent2(self, n: int, text: str) -> tuple[str, dict[str, Any]]:
        msg = Message(message_id=uuid.uuid4().hex, role=Role.ROLE_USER)
        resumed = False
        if self.strategy == "stateful":
            msg.parts.append(Part(text=text))
            if self.context_id:
                msg.context_id = self.context_id
            if self.pending_task:
                msg.task_id, resumed = self.pending_task, True
        else:  # stateless: fresh context, the whole conversation pasted in
            msg.parts.append(Part(text=envelope(self.history, text)))
        sent_text = msg.parts[0].text

        self.transport.label = n
        t0 = time.time()
        state, answer, question = None, "", ""
        task_id = context_id = None
        async for ev in self.client.send_message(SendMessageRequest(message=msg)):
            d = to_dict(ev)
            append_jsonl(self.out / "client_received.jsonl", {"t": time.time(), "turn": n, "event": d})
            for kind in ("task", "status_update", "artifact_update"):
                obj = d.get(kind)
                if not obj:
                    continue
                task_id = obj.get("id") or obj.get("task_id") or task_id
                context_id = obj.get("context_id") or context_id
                status = obj.get("status") or {}
                if status.get("state"):
                    state = status["state"]
                if status.get("message"):
                    question = " ".join(p.get("text", "") for p in status["message"].get("parts", []))
                if kind == "artifact_update":
                    answer += " ".join(p.get("text", "") for p in obj["artifact"].get("parts", []))
        latency = (time.time() - t0) * 1000

        if task_id and task_id not in self.task_ids:
            self.task_ids.append(task_id)
        if context_id and context_id not in self.context_ids:
            self.context_ids.append(context_id)
        if self.strategy == "stateful":
            self.context_id = context_id
        input_required = state == "TASK_STATE_INPUT_REQUIRED"
        self.pending_task = task_id if input_required else None

        wire = [w for w in read_jsonl(self.out / "wire.jsonl") if w.get("label") == n]
        return (question if input_required else answer), {
            "state": state.replace("TASK_STATE_", "").lower() if state else None,
            "chars_sent": len(sent_text),
            "bytes_out": sum(w["bytes"] for w in wire if w["dir"] == "out"),
            "bytes_in": sum(w["bytes"] for w in wire if w["dir"] == "in"),
            "latency_ms": round(latency, 1),
            "resumed_task": resumed,
            "task_id": task_id,
            "context_id": context_id,
        }


async def run_strategy(url: str, strategy: str, out: Path) -> tuple[list[dict], EntryAgent, dict[str, str]]:
    transport = TeeTransport(out / "wire.jsonl")
    http = httpx.AsyncClient(transport=transport, timeout=120)
    client = await create_client(url, ClientConfig(streaming=True, httpx_client=http))
    agent1 = EntryAgent(client, transport, strategy, out)
    records = []
    for n, turn in enumerate(TURNS, 1):
        rec = await agent1.handle(n, turn)
        records.append(rec)
        append_jsonl(out / "turns.jsonl", rec)
    transport.label = "final-check"
    final_states = {}
    for tid in agent1.task_ids:  # what state is every task Agent 2 holds left in?
        task = to_dict(await client.get_task(GetTaskRequest(id=tid)))
        final_states[tid] = task["status"]["state"].replace("TASK_STATE_", "").lower()
    await client.close()
    await http.aclose()
    return records, agent1, final_states


# --------------------------------------------------------------------------- metrics

def summarise(strategy: str, records: list[dict], agent1: EntryAgent, final_states: dict[str, str],
              gt: list[dict], memory_chars: int) -> dict[str, Any]:
    graded = [r for r in records if "correct" in r]
    calls = [r for r in records if r["a2a_calls"]]
    lookups = [g["content"]["input"]["query"] for g in gt
               if g["kind"] == "tool_call" and g["content"]["name"] == "lookup_fact"]
    inputs = [g for g in gt if g["kind"] == "input"]
    clar = next(r for r in records if TURNS[r["turn"] - 1].get("clarification"))
    answer = records[clar["turn"]]  # the user's reply to the clarifying question
    return {
        "strategy": strategy,
        "user_turns": len(records),
        "turns_sent_to_agent2": len(calls),
        "correct_answers": f"{sum(r['correct'] for r in graded)}/{len(graded)}",
        "a2a_calls": sum(r["a2a_calls"] for r in records),
        "a2a_contexts_created": len(agent1.context_ids),
        "a2a_tasks_created": len(agent1.task_ids),
        "tasks_left_input_required": sum(s == "input_required" for s in final_states.values()),
        "chars_sent_total": sum(r["chars_sent"] for r in calls),
        "chars_sent_first_call": calls[0]["chars_sent"],
        "chars_sent_last_call": calls[-1]["chars_sent"],
        "wire_bytes_out": sum(r["bytes_out"] for r in calls),
        "wire_bytes_in": sum(r["bytes_in"] for r in calls),
        "agent2_chars_read": sum(len(g["content"]) for g in inputs),
        "agent2_lookup_calls": len(lookups),
        "agent2_repeated_lookups": sum(c - 1 for c in Counter(lookups).values()),
        "agent2_calculate_calls": sum(1 for g in gt if g["kind"] == "tool_call"
                                      and g["content"]["name"] == "calculate"),
        "agent2_requests_replayed": sum(1 for g in gt if g["kind"] == "replay"),
        "agent2_figures_reused_from_history": sum(1 for g in gt if g["kind"] == "figure_reused"),
        "agent2_memory_held_chars": memory_chars,
        "latency_ms_total": round(sum(r["latency_ms"] for r in calls), 1),
        "latency_ms_last_call": calls[-1]["latency_ms"],
        "clarification_question_relayed": clar["state"] == "input_required",
        "clarification_answer_resumed_same_task": bool(answer.get("resumed_task")),
        "clarification_answer_chars_sent": answer["chars_sent"],
        "clarification_hops": "Agent 2 → Agent 1 → user → Agent 1 → Agent 2 (4)",
    }


def write_scorecard(root: Path, results: dict[str, dict]) -> str:
    s, l = results["stateful"]["summary"], results["stateless"]["summary"]
    rows = [k for k in s if k not in ("strategy", "clarification_hops")]
    lines = [
        "# e02 scorecard: multi-turn context through an entry-point agent",
        "",
        f"Run folder: `{root}`  ·  scripted user, scripted Agent 1, scripted Agent 2  ·  {s['user_turns']} user turns",
        "",
        "## Stateful (reuse contextId) vs stateless (resend full history)",
        "",
        "| Metric | Stateful | Stateless |",
        "|---|---|---|",
    ] + [f"| {k.replace('_', ' ')} | {s[k]} | {l[k]} |" for k in rows] + [
        "",
        "Clarification path (both strategies): " + s["clarification_hops"],
        "",
        "## Turn by turn",
        "",
        "| # | User says | Route | Stateful: chars sent | Stateless: chars sent | Stateful ok | Stateless ok |",
        "|---|---|---|---|---|---|---|",
    ]
    for a, b in zip(results["stateful"]["records"], results["stateless"]["records"]):
        ok = lambda r: "–" if "correct" not in r else ("✅" if r["correct"] else "❌")  # noqa: E731
        route = "Agent 1" if not a["a2a_calls"] else ("Agent 2 (clarify)" if a["state"] == "input_required"
                                                      else "Agent 2")
        lines.append(f"| {a['turn']} | {a['user']} | {route} | {a['chars_sent']} | {b['chars_sent']} | "
                     f"{ok(a)} | {ok(b)} |")
    md = "\n".join(lines) + "\n"
    (root / "scorecard.md").write_text(md)
    (root / "scorecard.json").write_text(json.dumps(results, indent=2, default=str))
    return md


# --------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> dict:
    argparse.ArgumentParser(prog="a2a-exp e02").parse_args(argv)
    root = new_run_dir(EXPERIMENT_ID, "stateful-vs-stateless")
    results = {}
    for strategy in STRATEGIES:
        out = root / strategy
        out.mkdir()
        agent2 = ConversationalStatsAgent()  # a fresh Agent 2 (empty memory) per strategy
        with serve(lambda url: build_app(url, agent2, out / "ground_truth.jsonl")) as url:
            records, agent1, final_states = asyncio.run(run_strategy(url, strategy, out))
        memory = {k: vars(v) for k, v in agent2.memory.items()}
        memory_chars = len(json.dumps(memory)) if memory else 0
        summary = summarise(strategy, records, agent1, final_states,
                            read_jsonl(out / "ground_truth.jsonl"), memory_chars)
        results[strategy] = {"summary": summary, "records": records}
    print(write_scorecard(root, results))
    return {k: v["summary"] for k, v in results.items()}
