"""e03 · Amnesiac Agent 2.

Claim from e02: without Agent 2's memory, a stateful run would still look
healthy at the protocol level (valid IDs, completed tasks, no errors), but
every follow-up from turn 3 onwards would be answered wrongly.

Test: run e02's 17-turn stateful conversation (Agent 1 reuses the contextId)
against three Agent 2 versions and compare protocol health with correctness.

    uv run a2a-exp e03
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from ...core.recording import new_run_dir, serve
from ...core.remote_agent import build_app
from ..e02_multiturn_context.agent2 import ConversationalStatsAgent
from ..e02_multiturn_context.run import run_strategy
from ..e02_multiturn_context.scenario import TURNS
from .agents import AmnesiacAgent, GracefulAmnesiacAgent

EXPERIMENT_ID = "e03_amnesiac_agent2"
QUESTION = ("If Agent 2 silently has no memory behind the contextId, does the stateful conversation "
            "still look healthy at the protocol level while answering follow-ups wrongly?")

VARIANTS = {
    "control": (ConversationalStatsAgent, "e02's Agent 2, with memory"),
    "amnesiac": (AmnesiacAgent, "same code, memory wiped before every call"),
    "graceful": (GracefulAmnesiacAgent, "no memory, never crashes, always answers"),
}


def summarise(records: list[dict], final_states: dict[str, str]) -> dict[str, Any]:
    calls = [r for r in records if r["a2a_calls"]]
    graded = [r for r in records if "correct" in r]
    followups = [r for r in graded if r["turn"] >= 3]
    states = [r["state"] for r in calls]
    return {
        "a2a_calls": len(calls),
        "contexts_used": len({r["context_id"] for r in calls if r["context_id"]}),
        "every_call_got_task_id": all(r["task_id"] for r in calls),
        "tasks_completed": states.count("completed"),
        "tasks_input_required": states.count("input_required"),
        "tasks_failed": states.count("failed"),
        "client_side_errors": sum(1 for r in calls if r.get("error")),
        "tasks_still_open_at_end": sum(s not in ("completed", "failed", "canceled", "rejected")
                                       for s in final_states.values()),
        "correct_answers": f"{sum(r['correct'] for r in graded)}/{len(graded)}",
        "correct_followups_turn3_on": f"{sum(r['correct'] for r in followups)}/{len(followups)}",
        "wrong_but_completed": sum(1 for r in graded if not r["correct"] and r["state"] == "completed"),
        "wrong_and_visibly_failed": sum(1 for r in graded if not r["correct"] and r["state"] != "completed"),
    }


def cell(r: dict) -> str:
    if not r["a2a_calls"]:
        return "–"
    mark = "" if "correct" not in r else ("✅ " if r["correct"] else "❌ ")
    state = r["state"] or "no state"
    return f"{mark}{state}" + (" ⚠️ error" if r.get("error") else "")


def write_scorecard(root: Path, results: dict[str, dict]) -> str:
    names = list(results)
    sums = {n: results[n]["summary"] for n in names}
    lines = [
        "# e03 scorecard: amnesiac Agent 2",
        "",
        f"Run folder: `{root}`  ·  e02's 17-turn conversation, stateful strategy (Agent 1 reuses the contextId)",
        "",
        "| Agent 2 version | What it is |",
        "|---|---|",
    ] + [f"| {n} | {VARIANTS[n][1]} |" for n in names] + [
        "",
        "## Protocol health vs correctness",
        "",
        "| Metric | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]
    for k in sums[names[0]]:
        lines.append(f"| {k.replace('_', ' ')} | " + " | ".join(str(sums[n][k]) for n in names) + " |")
    lines += ["", "## Turn by turn", "",
              "| # | User says | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
    for i, turn in enumerate(TURNS):
        lines.append(f"| {i + 1} | {turn['text']} | " + " | ".join(cell(results[n]["records"][i]) for n in names) + " |")
    lines += ["", "## What Agent 1 was told (no-memory versions)", "",
              "| # | User says | amnesiac replied | graceful replied |", "|---|---|---|---|"]
    for i, turn in enumerate(TURNS):
        a, g = results["amnesiac"]["records"][i], results["graceful"]["records"][i]
        if a["a2a_calls"]:
            short = lambda r: (r["reply"] or f"(nothing: {r['error'] or r['state']})")[:90].replace("|", "/")  # noqa: E731
            lines.append(f"| {i + 1} | {turn['text']} | {short(a)} | {short(g)} |")
    md = "\n".join(lines) + "\n"
    (root / "scorecard.md").write_text(md)
    (root / "scorecard.json").write_text(json.dumps(results, indent=2, default=str))
    return md


def main(argv: list[str] | None = None) -> dict:
    argparse.ArgumentParser(prog="a2a-exp e03").parse_args(argv)
    root = new_run_dir(EXPERIMENT_ID, "control-vs-amnesiac")
    results = {}
    for name, (cls, _) in VARIANTS.items():
        out = root / name
        out.mkdir()
        agent2 = cls()
        with serve(lambda url: build_app(url, agent2, out / "ground_truth.jsonl")) as url:
            records, _agent1, final_states = asyncio.run(run_strategy(url, "stateful", out))
        results[name] = {"summary": summarise(records, final_states), "records": records}
    print(write_scorecard(root, results))
    return {n: r["summary"] for n, r in results.items()}
