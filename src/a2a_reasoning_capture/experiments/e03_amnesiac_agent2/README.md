# e03 · Amnesiac Agent 2

## Question

e02 found that the stateful strategy only works because Agent 2 *chooses* to remember
behind the `contextId`. So the claim to test:

> Without Agent 2's memory, a stateful run would still look healthy at the protocol
> level (valid IDs, completed tasks, no errors), but every follow-up from turn 3
> onwards would be answered wrongly.

## Hypothesis

The follow-ups break, and Agent 1 can't tell from the protocol. One doubt going in:
our scripted Agent 2 was never written to cope with missing state, so it might
*crash* on some turns rather than quietly answer wrong.

## What changed since e02

- **Agent 2's memory is now the variable.** e02's 17-turn conversation is rerun with
  the stateful strategy only (Agent 1 reuses the `contextId`) against three versions
  of Agent 2:

  | Version | What it is |
  |---|---|
  | `control` | e02's Agent 2, with its memory |
  | `amnesiac` | The same code, with memory wiped before every call ([`agents.py`](agents.py)) |
  | `graceful` | No memory, and never crashes: if its code fails, it still answers. Closer to an LLM agent missing context |

- **Agent 1 now records protocol-level failures.** e02's Agent 1 records any error the
  A2A client raises and the task state it last saw. e01 and e02 reproduce unchanged.

## How to run

```bash
uv run a2a-exp e03
```

Results go to `runs/e03_amnesiac_agent2/<timestamp>-control-vs-amnesiac/`, with one
subfolder per version and a shared `scorecard.md`. The amnesiac run prints Agent 2's
server-side tracebacks to the console; that's expected.

## Results

| | control | amnesiac | graceful |
|---|---|---|---|
| Same `contextId` on every call | ✅ (1 context) | ✅ (1 context) | ✅ (1 context) |
| Every call got a task ID | ✅ | ✅ | ✅ |
| Tasks completed (+1 clarification) | 12 + 1 | 6 + 1 | 12 + 1 |
| Errors Agent 1 saw | 0 | **6** | **0** |
| Correct follow-ups, turn 3 onwards | 12/12 | 1/12* | 1/12* |
| **Wrong, but reported "completed"** | 0 | **5** | **11** |
| Wrong, with a visible error | 0 | 6 | 0 |

\* The one "correct" follow-up is a false pass. On turn 8 the check only looks for
"Finland" in Agent 2's clarifying question, and the amnesiac versions asked
"Which country do you mean: **Norway**, Denmark, Sweden, Finland or Iceland?". Offering
Norway, which is already in the set, gives the memory loss away. So in truth it's **0/12**.

What the graceful (no-crash) Agent 2 told Agent 1, all reported as `completed`:

| Turn | User says | Agent 2 replied | Kind of wrong |
|---|---|---|---|
| 3 | Now add Sweden. | Sweden 10,550,000. Combined: 10,550,000. Shares: Sweden 100.0%. | **Confident and plausible** |
| 5 | Which of those is the largest? | I don't have enough information to work that out. | Honest, but still "completed" |
| 9 | Finland | I can only help with population figures for Nordic countries. | Lost the paused question |
| 12 | List the populations we're working with. | . | Empty |
| 13 | Add Iceland as well. | Iceland 390,000. Combined: 390,000. Shares: Iceland 100.0%. | **Confident and plausible** |
| 15 | Drop Iceland and Finland, and add Denmark back. | Denmark 5,960,000. Combined: 5,960,000. Shares: Denmark 100.0%. | **Confident and plausible** |

(Turns 6, 7, 11, 14 and 16 also got "I don't have enough information".)

## What we learned

- **The claim holds, with one qualification.** Every follow-up was wrong without memory.
  The protocol looked perfectly healthy (same `contextId`, valid task IDs, every task
  `completed`, zero errors), *as long as Agent 2 doesn't crash*. The graceful version
  got 11 wrong answers through with no signal at all.
- **Crashing is the lucky case.** The amnesiac version raised errors on 6 turns, which
  Agent 1 saw as an A2A `InternalError`. But it still delivered 5 wrong answers as
  `completed`. Those errors happened by accident (empty lists, missing totals), not
  because anything detected the lost memory.
- **The most dangerous answers look the most normal.** "Combined: 10,550,000" after
  "Now add Sweden" is well-formed, confident, and wrong. Nothing in A2A (task state,
  IDs, schema) separates it from a right answer. Only knowing the conversation does.
- **"Completed" means "finished", not "right".** Even "I don't have enough information"
  came back as `completed`. A2A's task state reports on the task's lifecycle, not on the
  answer's quality. Agent 1 would have to read the text to notice.
- **A paused question needs memory too.** Resuming turn 9 on the paused task's `taskId`
  went through fine at the protocol level, but Agent 2 had forgotten what it asked,
  so "Finland" meant nothing to it.
- **Loose checks can be fooled.** Our own turn-8 check passed an answer that actually
  revealed the bug. Useful to remember for the evals experiment.

## Caveats

- Agent 2 is scripted. "Graceful" stands in for an LLM missing context. A real LLM might
  instead ask a clarifying question (`input-required`) or guess differently, but its
  answers would still reach Agent 1 as `completed`.
- The memory is wiped on *every* call, the most extreme case. A real failure (restart,
  eviction, expiry) would hit mid-conversation, and everything before it would look fine.

## Next question

If wrong answers look exactly like right ones at the protocol level, how do you
**evaluate** Agent 2 when you can only reach it through A2A? → **e04**
