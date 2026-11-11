# e02 scorecard: multi-turn context through an entry-point agent

Run folder: `runs/e02_multiturn_context/20261111-092904-stateful-vs-stateless`  ·  scripted user, scripted Agent 1, scripted Agent 2  ·  17 user turns

## Stateful (reuse contextId) vs stateless (resend full history)

| Metric | Stateful | Stateless |
|---|---|---|
| user turns | 17 | 17 |
| turns sent to agent2 | 13 | 13 |
| correct answers | 13/13 | 13/13 |
| a2a calls | 13 | 13 |
| a2a contexts created | 1 | 13 |
| a2a tasks created | 12 | 13 |
| tasks left input required | 0 | 1 |
| chars sent total | 437 | 14622 |
| chars sent first call | 53 | 227 |
| chars sent last call | 37 | 2055 |
| wire bytes out | 3996 | 17776 |
| wire bytes in | 18720 | 33620 |
| agent2 chars read | 437 | 14622 |
| agent2 lookup calls | 5 | 5 |
| agent2 repeated lookups | 0 | 0 |
| agent2 calculate calls | 6 | 6 |
| agent2 requests replayed | 0 | 108 |
| agent2 figures reused from history | 0 | 44 |
| agent2 memory held chars | 285 | 0 |
| latency ms total | 39.5 | 57.3 |
| latency ms last call | 2.8 | 3.9 |
| clarification question relayed | True | True |
| clarification answer resumed same task | True | False |
| clarification answer chars sent | 7 | 1011 |

Clarification path (both strategies): Agent 2 → Agent 1 → user → Agent 1 → Agent 2 (4)

## Turn by turn

| # | User says | Route | Stateful: chars sent | Stateless: chars sent | Stateful ok | Stateless ok |
|---|---|---|---|---|---|---|
| 1 | Hi! I'm putting together some notes on the Nordic countries. | Agent 1 | 0 | 0 | – | – |
| 2 | What's the combined population of Norway and Denmark? | Agent 2 | 53 | 227 | ✅ | ✅ |
| 3 | Now add Sweden. | Agent 2 | 15 | 354 | ✅ | ✅ |
| 4 | Thanks, that's really helpful. | Agent 1 | 0 | 0 | – | – |
| 5 | Which of those is the largest? | Agent 2 | 30 | 590 | ✅ | ✅ |
| 6 | Remove Denmark and recompute. | Agent 2 | 29 | 699 | ✅ | ✅ |
| 7 | What share of that is Norway? | Agent 2 | 29 | 839 | ✅ | ✅ |
| 8 | Add the remaining Nordic country. | Agent 2 (clarify) | 33 | 932 | ✅ | ✅ |
| 9 | Finland | Agent 2 | 7 | 1011 | ✅ | ✅ |
| 10 | Interesting. Is it cold there this time of year? | Agent 1 | 0 | 0 | – | – |
| 11 | How does the total now compare with the very first total I asked about? | Agent 2 | 71 | 1324 | ✅ | ✅ |
| 12 | List the populations we're working with. | Agent 2 | 40 | 1444 | ✅ | ✅ |
| 13 | Add Iceland as well. | Agent 2 | 20 | 1536 | ✅ | ✅ |
| 14 | Which is the smallest now? | Agent 2 | 26 | 1738 | ✅ | ✅ |
| 15 | Drop Iceland and Finland, and add Denmark back. | Agent 2 | 47 | 1873 | ✅ | ✅ |
| 16 | Is that the same as an earlier total? | Agent 2 | 37 | 2055 | ✅ | ✅ |
| 17 | Great, that's all for today. Thanks! | Agent 1 | 0 | 0 | – | – |
