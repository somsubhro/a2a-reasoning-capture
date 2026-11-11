# e01 · Opaque baseline

## Question

With A2A's default behaviour, how much of Agent 2's reasoning loop (thinking,
tool calls, tool results, intermediate text, order and timing) can Agent 1 see?

## Hypothesis

Very little. A2A agents are deliberately opaque to each other, so only the
final answer should cross the wire.

## What changed

Nothing: this is the starting point.

## Setup

```
Agent 1 (client, records everything)  ──A2A──▶  Agent 2 (Nordic stats agent)
                                                  think → lookup_fact → … → calculate → answer
```

- **Agent 2** runs a scripted think → tool → think → answer loop and writes every
  step to `ground_truth.jsonl`. Only the final answer leaves it, as an artifact.
- **Agent 1** sends two turns on the same `contextId`, records every streamed event,
  re-fetches each finished task with `get_task` (full history), and records the raw HTTP traffic.
- **Scoring** looks for each ground-truth step anywhere in what Agent 1 received.

The two turns:

```
1. What is the combined population of Norway and Denmark, and what share is each?
2. Now add Sweden to that and recompute.        ← only answerable if Agent 2 remembers turn 1
```

## How to run

```bash
uv run a2a-exp e01
uv run a2a-exp e01 --reasoner claude   # needs ANTHROPIC_API_KEY
```

Results go to `runs/e01_opaque_baseline/<timestamp>-opaque-<reasoner>/`.

## Results

| Step type | In Agent 2's loop | Seen by Agent 1 |
|---|---|---|
| Thinking | 4 | 0 |
| Tool calls | 5 | 0 |
| Tool results | 5 | 0 |
| Intermediate text | 2 | 0 |
| Final answer | 2 | 2 |

- **0 of 16 intermediate steps** reached Agent 1.
- Per turn, Agent 1 got 4 events: task submitted → working (no message) → answer artifact → completed.
- `get_task` with full history returned only the user's own message.
- Multi-turn worked: turn 2 reused the `contextId`, and Agent 2 remembered Norway and Denmark.

## What we learned

- By default, capturing Agent 2's loop isn't hard or easy: there is simply nothing to capture.
  A2A stores no internal steps unless the agent chooses to publish them.
- Multi-turn memory lives entirely inside Agent 2, keyed by `contextId`. Agent 1 can only
  infer it from a correct answer.

## Next question

If the user only ever talks to Agent 1, how efficient is a multi-turn conversation
when Agent 1 relies on Agent 2's memory versus resending the history itself? → **e02**
