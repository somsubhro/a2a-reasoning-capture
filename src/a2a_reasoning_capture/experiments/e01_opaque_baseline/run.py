"""e01 · Opaque baseline.

Agent 1 talks to a default (opaque) Agent 2 over A2A for two turns, records
everything it receives, then scores how much of Agent 2's reasoning loop it saw.

    uv run a2a-exp e01
    uv run a2a-exp e01 --reasoner claude
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path

import httpx
from a2a.client import ClientConfig, create_client
from a2a.types.a2a_pb2 import (
    GetTaskRequest,
    Message,
    Part,
    Role,
    SendMessageConfiguration,
    SendMessageRequest,
)

from ...core.reasoners import make_reasoner
from ...core.recording import TeeTransport, append_jsonl, new_run_dir, read_jsonl, serve, to_dict
from ...core.remote_agent import build_app
from ...core.scoring import score_capture

EXPERIMENT_ID = "e01_opaque_baseline"
QUESTION = "With A2A's default (opaque) behaviour, how much of Agent 2's reasoning loop can Agent 1 see?"

TURNS = [
    "What is the combined population of Norway and Denmark, and what share is each?",
    "Now add Sweden to that and recompute.",  # only answerable if Agent 2 remembers turn 1
]


async def agent1(url: str, out: Path) -> list[dict]:
    received = out / "client_received.jsonl"
    http = httpx.AsyncClient(transport=TeeTransport(out / "wire.jsonl"), timeout=120)
    client = await create_client(url, ClientConfig(streaming=True, httpx_client=http))
    context_id = None
    turns = []
    for i, text in enumerate(TURNS, 1):
        msg = Message(message_id=uuid.uuid4().hex, role=Role.ROLE_USER, parts=[Part(text=text)])
        if context_id:
            msg.context_id = context_id  # continue the same A2A conversation
        req = SendMessageRequest(message=msg, configuration=SendMessageConfiguration(history_length=100))
        task_id = None
        t0 = time.time()
        async for ev in client.send_message(req):
            d = to_dict(ev)
            append_jsonl(received, {"t": time.time(), "turn": i, "source": "stream", "event": d})
            for kind in ("task", "status_update", "artifact_update", "message"):
                if kind in d:
                    obj = d[kind]
                    task_id = obj.get("id") or obj.get("task_id") or task_id
                    context_id = obj.get("context_id") or context_id
        # After the turn: ask for the task again, with full history (post-hoc recovery path)
        task = await client.get_task(GetTaskRequest(id=task_id, history_length=100))
        append_jsonl(received, {"t": time.time(), "turn": i, "source": "get_task", "event": to_dict(task)})
        turns.append({"turn": i, "task_id": task_id, "context_id": context_id, "seconds": time.time() - t0})
    await client.close()
    await http.aclose()
    return turns


def write_scorecard(out: Path, reasoner: str, turns: list[dict], s: dict) -> str:
    sm = s["summary"]
    gt = read_jsonl(out / "ground_truth.jsonl")
    final_t2 = next(g["content"] for g in gt if g["kind"] == "final" and g["task_id"] == turns[1]["task_id"])
    sm["same_context_id_both_turns"] = turns[0]["context_id"] == turns[1]["context_id"]
    sm["agent2_remembered_turn1"] = all(c in final_t2 for c in ("Norway", "Denmark", "Sweden"))

    lines = [
        f"# A2A reasoning-capture scorecard: `opaque` mode, `{reasoner}` reasoner",
        "",
        f"Run folder: `{out}`",
        "",
        "## By step type",
        "",
        "| Step type | Steps in Agent 2's loop | Seen by Agent 1 | % | via stream | via get_task |",
        "|---|---|---|---|---|---|",
    ]
    for k, v in s["by_kind"].items():
        lines.append(f"| {k} | {v['steps']} | {v['recovered']} | {v['pct']}% | {v['via_stream']} | {v['via_get_task']} |")
    lines += ["", "## Overall", "", "| Metric | Value |", "|---|---|"]
    for k, v in sm.items():
        lines.append(f"| {k.replace('_', ' ')} | {v} |")
    lines += ["", "## Step by step", "", "| Turn task | # | Type | Seen? | Delay ms | Content |", "|---|---|---|---|---|---|"]
    for p in s["per_step"]:
        turn = 1 if p["task_id"] == turns[0]["task_id"] else 2
        lines.append(f"| {turn} | {p['seq']} | {p['kind']} | {'yes' if p['recovered'] else 'no'} | "
                     f"{p['delay_ms'] if p['delay_ms'] is not None else '–'} | {p['text'].replace('|', '/')} |")
    md = "\n".join(lines) + "\n"
    (out / "scorecard.md").write_text(md)
    (out / "scorecard.json").write_text(json.dumps({"mode": "opaque", "reasoner": reasoner, "turns": turns, **s}, indent=2))
    return md


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(prog="a2a-exp e01")
    ap.add_argument("--reasoner", choices=["scripted", "claude"], default="scripted")
    args = ap.parse_args(argv)

    out = new_run_dir(EXPERIMENT_ID, f"opaque-{args.reasoner}")
    reasoner = make_reasoner(args.reasoner)
    with serve(lambda url: build_app(url, reasoner, out / "ground_truth.jsonl")) as url:
        turns = asyncio.run(agent1(url, out))
    scores = score_capture(out)
    print(write_scorecard(out, args.reasoner, turns, scores))
    return scores["summary"]
