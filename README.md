# A2A reasoning-capture experiments

A lab notebook of small, reproducible experiments on what actually crosses the
[A2A protocol](https://a2a-protocol.org) boundary between two agents: reasoning,
context, multi-turn state.

Every experiment uses the same cast:

```
User ──▶ Agent 1 (entry point / client)  ──A2A──▶  Agent 2 (Nordic stats agent with tools)
```

## Experiments

Read them in order: each one's "next question" is the next one's starting point.

| # | Experiment | Question | Finding | Tag |
|---|---|---|---|---|
| e01 | [Opaque baseline](src/a2a_reasoning_capture/experiments/e01_opaque_baseline/README.md) | With A2A's default behaviour, how much of Agent 2's reasoning loop can Agent 1 see? | None of it: 0 of 16 intermediate steps. Only final answers cross the wire. | `e01-opaque-baseline` |
| e02 | [Multi-turn context](src/a2a_reasoning_capture/experiments/e02_multiturn_context/README.md) | If the user only talks to Agent 1, how efficient is multi-turn when Agent 1 relies on Agent 2's memory (`contextId`) versus resending the history? | Both got 13/13 follow-ups right. Resending history cost 33× more and kept growing, and left a clarification task orphaned. Reusing `contextId` is cheap but makes Agent 1 trust memory it can't see. | `e02-multiturn-context` |
| e03 | [Amnesiac Agent 2](src/a2a_reasoning_capture/experiments/e03_amnesiac_agent2/README.md) | If Agent 2 silently has no memory behind the `contextId`, does the conversation still look healthy at the protocol level? | Yes. Every follow-up was wrong, yet with a non-crashing Agent 2 all 11 wrong answers came back `completed`, with the same `contextId`, valid IDs and no errors. Only a crashing Agent 2 produced any errors, and only by accident. | `e03-amnesiac-agent2` |

## Running

Needs [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed automatically).

```bash
uv sync
uv run a2a-exp list     # every experiment and its question
uv run a2a-exp e01      # run one experiment
uv run a2a-exp all      # re-run everything, in order
```

Each run writes to `runs/<experiment>/<timestamp>-<label>/`:

| File | What it holds |
|---|---|
| `ground_truth.jsonl` | Every step Agent 2 actually took (what *could* be captured) |
| `client_received.jsonl` | Every A2A event Agent 1 received |
| `wire.jsonl` | Raw HTTP traffic between the agents |
| `scorecard.md` / `.json` | The results |

Agent 2's brain is scripted by default (repeatable, free). `--reasoner claude`
swaps in Claude Opus 5.5 where an experiment supports it (needs `ANTHROPIC_API_KEY`).

## Layout

```
src/a2a_reasoning_capture/
  core/                 shared by every experiment
    reasoners.py          Agent 2's tools and brains (scripted, Claude)
    remote_agent.py       Agent 2's A2A server (opaque; supports input-required)
    recording.py          run folders, JSONL logs, raw-HTTP recorder, local server
    scoring.py            ground truth vs what Agent 1 received
  experiments/
    eNN_<name>/           one folder per experiment: README.md + run.py
  cli.py                the a2a-exp command
runs/                   committed results, one folder per experiment
```

## Adding an experiment

1. Copy the README template from an existing experiment: Question → Hypothesis →
   What changed → Setup → How to run → Results → What we learned → Next question.
2. Add `run.py` with `EXPERIMENT_ID`, `QUESTION` and `main(argv)`.
3. Register it in `experiments/__init__.py` and add a row to the table above.
4. Make sure `uv run a2a-exp all` still passes, then commit and tag it `eNN-<name>`.
