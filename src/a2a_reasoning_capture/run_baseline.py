"""Run the baseline: Agent 1 talks to Agent 2 over A2A for two turns,
records everything it receives, then scores capture of Agent 2's reasoning loop.

    uv run python -m a2a_capture.run_baseline            # scripted reasoner
    uv run python -m a2a_capture.run_baseline --reasoner claude
"""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import uvicorn
from a2a.client import ClientConfig, create_client
from a2a.types.a2a_pb2 import (
    GetTaskRequest,
    Message,
    Part,
    Role,
    SendMessageConfiguration,
    SendMessageRequest,
)
from google.protobuf.json_format import MessageToDict

from .reasoners import step_text
from .remote_agent import build_app

PORT = 9999
URL = f"http://127.0.0.1:{PORT}"
TURNS = [
    "What is the combined population of Norway and Denmark, and what share is each?",
    "Now add Sweden to that and recompute.",  # only answerable if Agent 2 remembers turn 1
]


# --------------------------------------------------------------------------- recording

class TeeTransport(httpx.AsyncBaseTransport):
    """Wraps the real transport and records raw bytes going over the wire."""

    def __init__(self, path: Path) -> None:
        self.inner = httpx.AsyncHTTPTransport()
        self.path = path

    def _log(self, rec: dict) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        body = request.content.decode(errors="replace")
        self._log({"t": time.time(), "dir": "out", "method": request.method,
                   "url": str(request.url), "bytes": len(request.content), "body": body})
        resp = await self.inner.handle_async_request(request)
        log = self._log

        class Stream(httpx.AsyncByteStream):
            async def __aiter__(self):
                async for chunk in resp.stream:
                    log({"t": time.time(), "dir": "in", "bytes": len(chunk),
                         "body": chunk.decode(errors="replace")})
                    yield chunk

            async def aclose(self):
                await resp.aclose()

        return httpx.Response(resp.status_code, headers=resp.headers, stream=Stream(),
                              extensions=resp.extensions, request=request)


def to_dict(msg) -> dict:
    return MessageToDict(msg, preserving_proto_field_name=True)


# --------------------------------------------------------------------------- Agent 1

async def agent1(out: Path) -> list[dict]:
    received = out / "client_received.jsonl"
    http = httpx.AsyncClient(transport=TeeTransport(out / "wire.jsonl"), timeout=120)
    client = await create_client(URL, ClientConfig(streaming=True, httpx_client=http))
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
            with received.open("a") as f:
                f.write(json.dumps({"t": time.time(), "turn": i, "source": "stream", "event": d}) + "\n")
            for kind in ("task", "status_update", "artifact_update", "message"):
                if kind in d:
                    obj = d[kind]
                    task_id = obj.get("id") or obj.get("task_id") or task_id
                    context_id = obj.get("context_id") or context_id
        # After the turn: ask for the task again, with full history (post-hoc recovery path)
        task = await client.get_task(GetTaskRequest(id=task_id, history_length=100))
        with received.open("a") as f:
            f.write(json.dumps({"t": time.time(), "turn": i, "source": "get_task", "event": to_dict(task)}) + "\n")
        turns.append({"turn": i, "task_id": task_id, "context_id": context_id, "seconds": time.time() - t0})
    await client.close()
    await http.aclose()
    return turns


# --------------------------------------------------------------------------- scoring

def leaves(v) -> list[str]:
    if isinstance(v, dict):
        return [x for val in v.values() for x in leaves(val)]
    if isinstance(v, list):
        return [x for val in v for x in leaves(val)]
    return [str(v)]


def score(out: Path, turns: list[dict]) -> dict:
    gt = [json.loads(l) for l in (out / "ground_truth.jsonl").read_text().splitlines()]
    rx = [json.loads(l) for l in (out / "client_received.jsonl").read_text().splitlines()]
    wire = [json.loads(l) for l in (out / "wire.jsonl").read_text().splitlines()]

    # each received event as text, in arrival order
    rx_text = [(r["t"], r["source"], json.dumps(r["event"])) for r in rx]

    def find(step) -> tuple[float | None, int | None, set[str]]:
        needles = [step["content"]] if isinstance(step["content"], str) else leaves(step["content"])
        needles = [json.dumps(n)[1:-1] for n in needles]  # match JSON-escaped form
        first_t, first_idx, sources = None, None, set()
        for idx, (t, src, text) in enumerate(rx_text):
            if all(n in text for n in needles):
                sources.add(src)
                if first_t is None:
                    first_t, first_idx = t, idx
        return first_t, first_idx, sources

    per_step = []
    for s in gt:
        t, idx, sources = find(s)
        per_step.append({"seq": s["seq"], "task_id": s["task_id"], "kind": s["kind"],
                         "recovered": t is not None, "via": sorted(sources),
                         "delay_ms": None if t is None else round((t - s["t"]) * 1000, 1),
                         "arrival_idx": idx, "text": step_text(s)[:80]})

    kinds = ["thinking", "tool_call", "tool_result", "text", "final"]
    by_kind = {}
    for k in kinds:
        rows = [p for p in per_step if p["kind"] == k]
        if rows:
            hit = [p for p in rows if p["recovered"]]
            by_kind[k] = {"steps": len(rows), "recovered": len(hit),
                          "pct": round(100 * len(hit) / len(rows)),
                          "via_stream": sum("stream" in p["via"] for p in hit),
                          "via_get_task": sum("get_task" in p["via"] for p in hit)}

    hits = [p for p in per_step if p["recovered"]]
    order_ok = all(a["arrival_idx"] <= b["arrival_idx"] for a, b in zip(hits, hits[1:]))
    nonfinal = [p for p in per_step if p["kind"] != "final"]
    delays = [p["delay_ms"] for p in hits]

    final_t2 = next(s["content"] for s in gt if s["kind"] == "final" and s["task_id"] == turns[1]["task_id"])
    return {
        "per_step": per_step,
        "by_kind": by_kind,
        "summary": {
            "ground_truth_steps": len(per_step),
            "recovered_steps": len(hits),
            "recovered_pct": round(100 * len(hits) / len(per_step)),
            "intermediate_steps_recovered": f"{sum(p['recovered'] for p in nonfinal)}/{len(nonfinal)}",
            "order_preserved_for_recovered": order_ok,
            "min_delay_ms": min(delays) if delays else None,
            "max_delay_ms": max(delays) if delays else None,
            "stream_events_received": sum(r["source"] == "stream" for r in rx),
            "wire_bytes_in": sum(w["bytes"] for w in wire if w["dir"] == "in"),
            "wire_bytes_out": sum(w["bytes"] for w in wire if w["dir"] == "out"),
            "same_context_id_both_turns": turns[0]["context_id"] == turns[1]["context_id"],
            "agent2_remembered_turn1": all(c in final_t2 for c in ("Norway", "Denmark", "Sweden")),
        },
    }


def write_scorecard(out: Path, mode: str, reasoner: str, turns: list[dict], s: dict) -> str:
    sm = s["summary"]
    lines = [
        f"# A2A reasoning-capture scorecard: `{mode}` mode, `{reasoner}` reasoner",
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
    (out / "scorecard.json").write_text(json.dumps({"mode": mode, "reasoner": reasoner, "turns": turns, **s}, indent=2))
    return md


# --------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reasoner", choices=["scripted", "claude"], default="scripted")
    args = ap.parse_args()

    mode = "opaque"
    out = Path("runs") / f"{datetime.now():%Y%m%d-%H%M%S}-{mode}-{args.reasoner}"
    out.mkdir(parents=True)

    app = build_app(URL, args.reasoner, out / "ground_truth.jsonl")
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)

    try:
        turns = asyncio.run(agent1(out))
    finally:
        server.should_exit = True
    print(write_scorecard(out, mode, args.reasoner, turns, score(out, turns)))


if __name__ == "__main__":
    main()
