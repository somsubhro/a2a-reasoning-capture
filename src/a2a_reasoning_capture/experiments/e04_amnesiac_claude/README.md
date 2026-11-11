# e04 · Amnesiac Agent 2, with a real model

## Question

e03 used a scripted Agent 2. Without memory, its no-crash version quietly gave 11 wrong
answers, all reported `completed`. Does a **real model** behave the same way when there's
no memory behind the `contextId`? Does it guess confidently, ask, or admit it doesn't know?
And does the protocol still look healthy?

## Hypothesis

A capable model is less likely to invent a working set out of nothing, so it may ask
or say it doesn't know. That would make the failure *visible*, but through what
signal, and what would Agent 1 do with it?

## What changed since e03

- **Agent 2 is Claude Opus 5.5** ([`core/claude_agent.py`](../../core/claude_agent.py)) instead of a script:
  a tool-use loop over the same `lookup_fact` and `calculate` tools, adaptive thinking
  (summarised), effort `medium`, and server-side fallback if a request is refused.
- **An `ask_user` tool** lets Claude pause the A2A task in `input-required` with a
  question. Agent 1's reply comes back as that tool's result.
- **Two versions:** `control` keeps each conversation's full message history per
  `contextId`; `amnesiac` starts from a blank history on every call.
- **Real tokens, cost and latency** are recorded from every API call (`api_call` steps in `ground_truth.jsonl`).
- Same 17-turn conversation and same stateful Agent 1 as e02/e03. One run.

## How to run

Needs an Anthropic API key in a `.env` file at the repo root (gitignored):

```bash
uv run --env-file .env a2a-exp e04
```

`uv run a2a-exp all` skips e04 unless a key is set, so the free regression check never
spends money. This run cost **$0.41**.

## Results

| | control (remembers) | amnesiac (blank every call) |
|---|---|---|
| Same `contextId`, valid task IDs, protocol errors | ✅, ✅, 0 | ✅, ✅, 0 |
| Correct follow-ups (turn 3 on) | 11/12 by the check, **12/12 really*** | **0/12** |
| Wrong, but reported `completed` | 0 (after the regrade) | **1** |
| Paused to ask (`input-required`) | 1 (the genuine clarification) | **11** |
| A2A calls / separate tasks | 13 / 12 | 15 / **4** |
| Model API calls | 23 | 19 |
| Input / output tokens | 61,449 / 2,867 | 16,582 / 1,922 |
| Cost | $0.30 | $0.10 |
| Time for all turns (slowest turn) | 43 s (7.4 s) | 52 s (7.1 s) |

\* Turn 12 was graded wrong, but the reply was right: "Norway with 5,550,000, Sweden with
10,550,000 and Finland with 5,600,000". The check looked for the exact text
"Finland 5,600,000", and "Finland **with** 5,600,000" didn't match.

What the amnesiac told Agent 1 (selection):

| Turn | User says | Amnesiac Claude replied | Task state |
|---|---|---|---|
| 3 | Now add Sweden. | I don't have a working set of countries yet. Which countries should Sweden be added to? | `input-required` |
| 7 | What share of that is Norway? | Norway's share of what total? Which countries should be in the working set? | `input-required` |
| 9 | Finland | Your working set is now just Finland, with a population of 5,600,000 (2024 estimate). That's also the combined total, so Finland's share is 100.0%. | **`completed`, wrong** |
| 16 | Is that the same as an earlier total? | There's no earlier total in our conversation yet. Which countries' total should I compare…? | `input-required` |

How the A2A tasks were threaded (the amnesiac's 15 calls landed in only 4 tasks):

```
turn  3  "Now add Sweden."                → new task B, pauses: "which countries?"
turn  4  "Thanks, that's really helpful." → sent to Agent 2 as the answer to B   (small talk!)
turn  5  "Which of those is the largest?" → new task C, pauses
turns 6–9                                 → each sent as "the answer" to C, which pauses again…
turn 11  "How does the total compare…"    → new task D, pauses
turns 12–17 (incl. "Great, thanks!")      → all chained into D as "answers"
```

## What we learned

- **A real model failed differently from the script.** e03's no-crash script quietly
  answered wrong. Claude without memory mostly *said so*, in 11 of 12 follow-ups, and
  paused the task to ask. The failure became visible, through `input-required` rather
  than any error.
- **The silent failure still got through once.** On turn 9 the amnesiac had forgotten its
  own question, so it read "Finland" as a fresh request and answered confidently and wrongly
  ("working set is now just Finland… 100.0%"), reported `completed`. Rarer than e03, but
  the same kind of failure.
- **`input-required` moves the problem to Agent 1.** A2A signals *that* Agent 2 needs
  input, but deciding whether the user's next message *is* that input is entirely up to
  Agent 1. Our scripted Agent 1 assumed it always was. So small talk ("Thanks, that's
  really helpful") was sent to Agent 2 as an answer, and seven different requests got
  chained into one long paused task. A real entry-point agent has to make this routing call well.
- **Task state isn't a quality signal in either direction.** `completed` doesn't mean right
  (turn 9), and `input-required` doesn't mean broken: control's one genuine clarification
  looks the same on the wire as the amnesiac's eleven "I don't know"s.
- **Remembering has a real token cost.** Control re-reads its whole conversation every call,
  so its input grows turn by turn: 3.7× the amnesiac's input tokens over just 13 turns.
  This is e02's trade-off in real tokens: with memory, the cost moves to Agent 2.
- **Exact-text grading failed again, the other way round.** In e03 a loose check passed a
  revealing answer; here a strict check failed a correct one. Two experiments in a row, a
  string-match grader gave the wrong verdict. Evaluating a real model needs better grading.

## Caveats

- One run of one model (Claude Opus 5.5, effort `medium`). Real models vary between runs.
- Our scripted user never answers Agent 2's questions, which a real user would. Even so,
  an amnesiac Agent 2 would forget the answer by the next call.
- Cost covers only Agent 2's model calls (Agent 1 is scripted). Prompts were too short to
  benefit from prompt caching.
- The `ask_user` tool and system prompt invite Claude to ask when unsure; without them it
  might guess more often.

## Next question

String-matching graders have now misjudged answers in both directions, and task states
don't separate right from wrong. So how do you **evaluate** Agent 2 properly, when you
can only reach it through A2A? → **e05**
