"""a2a-exp: run the experiments.

    uv run a2a-exp list           # every experiment and the question it asks
    uv run a2a-exp e01            # run one experiment (extra args go to it)
    uv run a2a-exp all            # re-run every experiment, in order (a regression check;
                                  # paid ones are skipped unless an API key is set)
"""

from __future__ import annotations

import os
import sys

from .experiments import EXPERIMENTS, load


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "list"
    if cmd == "list":
        for short_id in EXPERIMENTS:
            mod = load(short_id)
            print(f"{short_id}  {mod.EXPERIMENT_ID:<28} {mod.QUESTION}")
        return
    if cmd == "all":
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
        for short_id in EXPERIMENTS:
            mod = load(short_id)
            print(f"\n===== {short_id} =====")
            if getattr(mod, "NEEDS_API_KEY", False) and not has_key:
                print("skipped: needs ANTHROPIC_API_KEY (paid model calls)")
                continue
            mod.main([])
        return
    if cmd not in EXPERIMENTS:
        sys.exit(f"unknown experiment {cmd!r}; try: list, all, {', '.join(EXPERIMENTS)}")
    load(cmd).main(args[1:])
