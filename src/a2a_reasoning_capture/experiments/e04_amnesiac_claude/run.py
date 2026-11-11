"""e04 · Amnesiac Agent 2, with a real model.

e03 again, but Agent 2 is Claude Opus 5.5 instead of a script:
* control  : Claude keeps each conversation's history per contextId
* amnesiac : Claude starts from a blank history on every call
Same 17-turn conversation, stateful strategy (Agent 1 reuses the contextId).

    uv run --env-file .env a2a-exp e04     # needs ANTHROPIC_API_KEY in .env
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from ...core.claude_agent import MODEL, ClaudeConversationalAgent
from ...core.recording import new_run_dir, read_jsonl, serve
from ...core.remote_agent import build_app
from ..e02_multiturn_context.run import run_strategy
from ..e02_multiturn_context.scenario import TURNS
from ..e03_amnesiac_agent2.run import cell
from ..e03_amnesiac_agent2.run import summarise as protocol_summary

EXPERIMENT_ID = "e04_amnesiac_claude"
NEEDS_API_KEY = True  # costs money: `a2a-exp all` skips it unless a key is set
QUESTION = ("With a real model as Agent 2 and no memory behind the contextId, does it guess, ask or admit "
            "it doesn't know, and does the protocol still look healthy?")

VARIANTS = {
    "control": (True, "Claude Opus 5.5, history kept per contextId"),
    "amnesiac": (False, "Claude Opus 5.5, blank history on every call"),
}


def per_call_costs(gt: list[dict]) -> list[dict[str, Any]]:
    """Group api_call steps by A2A call (each call starts with an 'input' record)."""
    calls: list[dict[str, Any]] = []
    for g in gt:
        if g["kind"] == "input":
            calls.append({"api_calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
                          "model_ms": 0.0, "tools": 0, "asked": 0})
        elif calls and g["kind"] == "api_call":
            c, u = calls[-1], g["content"]["usage"]
            c["api_calls"] += 1
            c["input_tokens"] += u["input_tokens"]
            c["output_tokens"] += u["output_tokens"]
            c["cost_usd"] += g["content"]["cost_usd"]
            c["model_ms"] += g["content"]["latency_ms"]
        elif calls and g["kind"] == "tool_call":
            calls[-1]["tools"] += 1
            calls[-1]["asked"] += g["content"]["name"] == "ask_user"
    return calls


def summarise(records: list[dict], final_states: dict[str, str], gt: list[dict]) -> dict[str, Any]:
    s = protocol_summary(records, final_states)
    calls = per_call_costs(gt)
    a2a = [r for r in records if r["a2a_calls"]]
    for r, c in zip(a2a, calls):  # attach per-turn cost to each A2A turn
        r.update(cost=c)
    models = sorted({g["content"]["model"] for g in gt if g["kind"] == "api_call"})
    s.update({
        "model_api_calls": sum(c["api_calls"] for c in calls),
        "input_tokens": sum(c["input_tokens"] for c in calls),
        "output_tokens": sum(c["output_tokens"] for c in calls),
        "input_tokens_last_turn": calls[-1]["input_tokens"] if calls else 0,
        "cost_usd": round(sum(c["cost_usd"] for c in calls), 4),
        "tool_calls": sum(c["tools"] for c in calls),
        "ask_user_calls": sum(c["asked"] for c in calls),
        "latency_s_total": round(sum(r["latency_ms"] for r in a2a) / 1000, 1),
        "latency_s_slowest_turn": round(max((r["latency_ms"] for r in a2a), default=0) / 1000, 1),
        "models_used": ", ".join(models),
    })
    return s


def write_scorecard(root: Path, results: dict[str, dict]) -> str:
    names = list(results)
    sums = {n: results[n]["summary"] for n in names}
    lines = [
        "# e04 scorecard: amnesiac Agent 2 with a real model",
        "",
        f"Run folder: `{root}`  ·  e02's 17-turn conversation, stateful strategy  ·  one run",
        "",
        "| Agent 2 version | What it is |", "|---|---|",
    ] + [f"| {n} | {VARIANTS[n][1]} |" for n in names] + [
        "", "## Protocol health, correctness and cost", "",
        "| Metric | " + " | ".join(names) + " |", "|---|" + "---|" * len(names),
    ]
    for k in sums[names[0]]:
        lines.append(f"| {k.replace('_', ' ')} | " + " | ".join(str(sums[n][k]) for n in names) + " |")
    lines += ["", "## Turn by turn", "",
              "| # | User says | " + " | ".join(f"{n} | {n} tokens in/out" for n in names) + " |",
              "|---|---|" + "---|---|" * len(names)]
    for i, turn in enumerate(TURNS):
        row = []
        for n in names:
            r = results[n]["records"][i]
            c = r.get("cost")
            row += [cell(r), f"{c['input_tokens']:,} / {c['output_tokens']:,}" if c else "–"]
        lines.append(f"| {i + 1} | {turn['text']} | " + " | ".join(row) + " |")
    lines += ["", "## What Agent 1 was told", ""]
    for i, turn in enumerate(TURNS):
        if not results[names[0]]["records"][i]["a2a_calls"]:
            continue
        lines.append(f"**{i + 1}. {turn['text']}**")
        for n in names:
            r = results[n]["records"][i]
            reply = (r["reply"] or f"(nothing: {r.get('error') or r['state']})").replace("\n", " ")
            lines.append(f"- *{n}* ({cell(r)}): {reply}")
        lines.append("")
    md = "\n".join(lines) + "\n"
    (root / "scorecard.md").write_text(md)
    (root / "scorecard.json").write_text(json.dumps(results, indent=2, default=str))
    return md


def main(argv: list[str] | None = None, client: Any = None) -> dict:
    argparse.ArgumentParser(prog="a2a-exp e04").parse_args(argv)
    if client is None and not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        sys.exit("e04 needs Claude API access. Put ANTHROPIC_API_KEY=... in a .env file at the repo root "
                 "(it is gitignored) and run:  uv run --env-file .env a2a-exp e04")
    root = new_run_dir(EXPERIMENT_ID, f"control-vs-amnesiac-{MODEL}")
    results = {}
    for name, (remember, _) in VARIANTS.items():
        out = root / name
        out.mkdir()
        agent2 = ClaudeConversationalAgent(remember=remember, client=client)
        with serve(lambda url: build_app(url, agent2, out / "ground_truth.jsonl")) as url:
            records, _agent1, final_states = asyncio.run(run_strategy(url, "stateful", out))
        summary = summarise(records, final_states, read_jsonl(out / "ground_truth.jsonl"))
        results[name] = {"summary": summary, "records": records}
    print(write_scorecard(root, results))
    return {n: r["summary"] for n, r in results.items()}
