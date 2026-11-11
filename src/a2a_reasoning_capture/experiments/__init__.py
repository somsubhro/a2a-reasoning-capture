"""Registry of experiments, in the order they were run.

Each experiment is a package `eNN_<slug>` with:
  * README.md : question, hypothesis, what changed, how to run, results, learnings, next question
  * run.py    : EXPERIMENT_ID, QUESTION, main(argv) -> summary dict
"""

from __future__ import annotations

import importlib

EXPERIMENTS = {
    "e01": "e01_opaque_baseline",
    "e02": "e02_multiturn_context",
    "e03": "e03_amnesiac_agent2",
}


def load(short_id: str):
    return importlib.import_module(f"{__name__}.{EXPERIMENTS[short_id]}.run")
