"""Capture scoring: how much of Agent 2's reasoning loop (ground truth) shows up
in what Agent 1 received."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .reasoners import step_text
from .recording import read_jsonl

LOOP_KINDS = ["thinking", "tool_call", "tool_result", "text", "final"]


def leaves(v: Any) -> list[str]:
    if isinstance(v, dict):
        return [x for val in v.values() for x in leaves(val)]
    if isinstance(v, list):
        return [x for val in v for x in leaves(val)]
    return [str(v)]


def score_capture(out: Path) -> dict[str, Any]:
    gt = [s for s in read_jsonl(out / "ground_truth.jsonl") if s["kind"] in LOOP_KINDS]
    rx = read_jsonl(out / "client_received.jsonl")
    wire = read_jsonl(out / "wire.jsonl")
    rx_text = [(r["t"], r["source"], json.dumps(r["event"])) for r in rx]

    def find(step):
        needles = [step["content"]] if isinstance(step["content"], str) else leaves(step["content"])
        needles = [json.dumps(n)[1:-1] for n in needles]  # match the JSON-escaped form
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

    by_kind = {}
    for k in LOOP_KINDS:
        rows = [p for p in per_step if p["kind"] == k]
        if rows:
            hit = [p for p in rows if p["recovered"]]
            by_kind[k] = {"steps": len(rows), "recovered": len(hit),
                          "pct": round(100 * len(hit) / len(rows)),
                          "via_stream": sum("stream" in p["via"] for p in hit),
                          "via_get_task": sum("get_task" in p["via"] for p in hit)}

    hits = [p for p in per_step if p["recovered"]]
    nonfinal = [p for p in per_step if p["kind"] != "final"]
    delays = [p["delay_ms"] for p in hits]
    return {
        "per_step": per_step,
        "by_kind": by_kind,
        "summary": {
            "ground_truth_steps": len(per_step),
            "recovered_steps": len(hits),
            "recovered_pct": round(100 * len(hits) / len(per_step)) if per_step else 0,
            "intermediate_steps_recovered": f"{sum(p['recovered'] for p in nonfinal)}/{len(nonfinal)}",
            "order_preserved_for_recovered": all(a["arrival_idx"] <= b["arrival_idx"]
                                                 for a, b in zip(hits, hits[1:])),
            "min_delay_ms": min(delays) if delays else None,
            "max_delay_ms": max(delays) if delays else None,
            "stream_events_received": sum(r["source"] == "stream" for r in rx),
            "wire_bytes_in": sum(w["bytes"] for w in wire if w["dir"] == "in"),
            "wire_bytes_out": sum(w["bytes"] for w in wire if w["dir"] == "out"),
        },
    }
