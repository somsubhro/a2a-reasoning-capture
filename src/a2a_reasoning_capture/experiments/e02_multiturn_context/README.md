# e02 · Multi-turn context through an entry-point agent

## Question

The user only ever talks to Agent 1. Agent 1 delegates some turns to Agent 2 over A2A.
How efficient is a long multi-turn conversation when Agent 1:

- **stateful:** relies on Agent 2's memory by reusing A2A's `contextId`, versus
- **stateless:** starts a fresh context every call and resends the whole conversation itself?

## Hypothesis

Both strategies can answer follow-ups correctly. Stateless should cost far more data
and repeated work on Agent 2's side, and the cost should grow with every turn.
Stateful should be cheap, but it puts all the memory inside Agent 2.

## What changed since e01

- **A real entry point.** e01's Agent 1 just forwarded two questions. Here Agent 1 holds
  its own conversation with a scripted user, answers small talk itself, and only
  delegates the turns that need Agent 2.
- **A longer, stateful conversation.** 17 user turns that keep editing a working set of
  countries ("add Sweden", "remove Denmark", "compare with the first total").
- **A clarification.** Agent 2 can pause a task with A2A's `input-required` state
  ("Which country do you mean?"). Agent 1 relays the question to the user and passes the
  answer back. The shared Agent 2 server in `core/` gained support for this.
- **Agent 1's context strategy is now the variable.** Each strategy gets a fresh Agent 2.

## Setup

```
User ⇄ Agent 1 (entry point: scripted routing, answers small talk)
            ⇅ A2A
       Agent 2 (scripted, conversational; tools: lookup_fact, calculate)
```

| | Stateful | Stateless |
|---|---|---|
| What Agent 1 sends | Only the new request | `[Conversation so far]` (every user and Agent 1 line) + `[Current request]` |
| `contextId` | The same one every call | A new one every call |
| Answering a clarification | Replies on the paused task's `taskId` | Sends a new message with the full history |
| Where the memory lives | Agent 2 (keyed by `contextId`) | The pasted history; Agent 2 replays every earlier request to rebuild its state |

When it rebuilds from history, Agent 2 reuses population figures it finds in earlier
answers instead of looking them up again. This is a design choice that favours
stateless (see "Caveats").

The conversation is in [`scenario.py`](scenario.py): 4 small-talk turns and 13 turns
for Agent 2, one of which triggers a clarification.

## How to run

```bash
uv run a2a-exp e02
```

Results go to `runs/e02_multiturn_context/<timestamp>-stateful-vs-stateless/`, with a
`stateful/` and a `stateless/` subfolder (`turns.jsonl`, `ground_truth.jsonl`,
`client_received.jsonl`, `wire.jsonl`) and a shared `scorecard.md`.

## Results

| Metric | Stateful | Stateless |
|---|---|---|
| Correct answers | 13/13 | 13/13 |
| A2A calls | 13 | 13 |
| Contexts created | 1 | 13 |
| Tasks created | 12 | 13 |
| Tasks left hanging in `input-required` | 0 | 1 |
| Characters Agent 1 sent (total) | 437 | 14,622 (**33×**) |
| Characters sent on the last call | 37 | 2,055 |
| Bytes on the wire, out / in | 3,996 / 18,720 | 17,776 / 33,620 |
| Earlier requests Agent 2 replayed | 0 | 108 |
| Figures Agent 2 re-read from history | 0 | 44 |
| Lookup tool calls / repeated lookups | 5 / 0 | 5 / 0 |
| State Agent 2 holds afterwards (chars) | 285 | 0 |
| Answering the clarification | 7 chars, same task resumed | 1,011 chars, new task |

How many characters each turn sent:

```
turn   stateful  stateless
  2         53        227
  3         15        354
  5         30        590
  9          7       1011   ← the one-word answer "Finland"
 13         20       1536
 16         37       2055
```

## What we learned

- **Multi-turn works either way, so correctness isn't the difference.** Both strategies
  got all 13 follow-ups right, including ones that depend on turns far back ("compare
  with the very first total").
- **Stateless costs grow with every turn, and the total grows faster still.**
  The message size grows roughly linearly per turn, so the total cost of the conversation
  grows roughly quadratically. By turn 16 one call carried 2,055 characters to deliver a
  37-character question. Agent 2 re-read and replayed 108 earlier requests in all. With a
  real LLM, that is 108 requests' worth of input tokens re-processed.
- **With these defaults, what you send comes straight back.** The first streamed event of
  every task is the Task object, including its message history, and our Agent 2 stores
  the incoming message there. Agent 1 never limited that history, so stateless paid
  twice: the whole history went out, then came straight back (inbound bytes 33,620 vs
  18,720). This isn't forced by A2A. A follow-up check showed that Agent 1 setting
  `history_length=0` on the request removes the echo, while Agent 2 still keeps the record.
  It only fixes the incoming half: stateless still has to *send* the whole history,
  because that's how it works without Agent 2's memory.
- **A2A's own tools fit the stateful pattern.** With `contextId`, a clarification is a
  7-character reply on the *same* paused task. Stateless can't resume a task without
  breaking its own rule, so it opens a new one and leaves the paused task hanging in
  `input-required` forever. Over a long conversation, those orphaned tasks pile up.
- **Stateful moves the cost and the risk to Agent 2.** Agent 1 sends almost nothing, but
  Agent 2 must hold state per `contextId` (285 characters here; far more with an LLM's
  history), and Agent 1 has to trust it. If Agent 2 restarts or evicts the context,
  follow-ups silently break, and from e01 we know Agent 1 can't see Agent 2's memory to check.
- **The protocol supplies the ID; the memory is a promise.** See "Who does the remembering?" below.

## Who does the remembering?

Stateful only worked because **we wrote Agent 2 to remember**. Neither A2A nor the SDK did it for us.

| Layer | What it provides | Remembers the conversation for Agent 2? |
|---|---|---|
| A2A protocol | `contextId`: a label meaning "these messages belong to one conversation" | No. It defines what the ID means, not that any memory sits behind it |
| A2A Python SDK | Generates IDs; keeps a task store (each task with its own messages) | Not automatically. Agent 2 receives the new message and the ID, plus the current task only when resuming an `input-required` one. Earlier tasks are passed in only if Agent 1 lists them in `reference_task_ids` *and* the server enables `should_populate_referred_tasks` (off by default), and even then turning them into memory is the agent's job |
| Our Agent 2 | `self.memory[context_id]`: a working state per conversation ([`agent2.py`](agent2.py)) | Yes, because we built it |

How it plays out across turns:

```
turn 2   Agent 1 → "combined population of Norway and Denmark?"   (no contextId)
         server creates ctx-abc · Agent 2 writes memory[ctx-abc] = {Norway, Denmark, totals…}
turn 3   Agent 1 → "Now add Sweden." + ctx-abc
         Agent 2 reads memory[ctx-abc], adds Sweden, writes it back
turn 9   Agent 1 → "Finland" + ctx-abc + taskId of the paused task   (resumes the clarification)
```

Without that notebook, the stateful run would still "work" at the protocol level (valid
IDs, completed tasks, no errors) but turn 3 onwards would be answered wrongly, because
"Now add Sweden" means nothing on its own.

Agent frameworks that support A2A commonly link `contextId` to their own session or
thread memory, so remembering often *feels* like a default. But that's the framework's
choice, and how much it keeps, for how long, and whether it survives a restart all vary
(not checked here for any specific framework). From Agent 1's side there's no way to
tell, which is e01's opacity again: **Agent 1 holds the ID; only Agent 2 knows whether
anything is behind it.**
- **Small talk leaks into stateless calls.** Agent 1 pasted its whole conversation,
  including turns that never involved Agent 2, so Agent 2 paid to read those too.
  A smarter stateless Agent 1 would filter the history, but that's a judgement call
  Agent 1 can get wrong.

## Caveats

- Everything is scripted, so this measures **protocol and context costs**, not LLM
  behaviour or speed. Latency here is local and tiny (under 5 ms a call) and isn't meaningful.
- Stateless is flattered: Agent 2 reuses figures from the pasted answers, so it never
  repeats a lookup. An LLM that distrusts pasted numbers would repeat tool calls.
- The A2A SDK logs `Dispatcher task is not running` once per run, while cleaning up a task
  that paused for input. All events arrived and every answer was correct, so it doesn't
  affect the results.
- The `history_length=0` fix was checked in a separate one-off test, not in this run's
  numbers. Not tested yet: a summarising stateless Agent 1.

## Next question

Stateful only works because Agent 2 chose to build memory behind the `contextId`.
If that memory silently isn't there, does anything at the protocol level tell
Agent 1? → **e03**
