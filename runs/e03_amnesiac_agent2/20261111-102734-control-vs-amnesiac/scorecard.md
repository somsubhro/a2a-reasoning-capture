# e03 scorecard: amnesiac Agent 2

Run folder: `runs/e03_amnesiac_agent2/20261111-102734-control-vs-amnesiac`  ·  e02's 17-turn conversation, stateful strategy (Agent 1 reuses the contextId)

| Agent 2 version | What it is |
|---|---|
| control | e02's Agent 2, with memory |
| amnesiac | same code, memory wiped before every call |
| graceful | no memory, never crashes, always answers |

## Protocol health vs correctness

| Metric | control | amnesiac | graceful |
|---|---|---|---|
| a2a calls | 13 | 13 | 13 |
| contexts used | 1 | 1 | 1 |
| every call got task id | True | True | True |
| tasks completed | 12 | 6 | 12 |
| tasks input required | 1 | 1 | 1 |
| tasks failed | 0 | 0 | 0 |
| client side errors | 0 | 6 | 0 |
| tasks still open at end | 0 | 0 | 0 |
| correct answers | 13/13 | 2/13 | 2/13 |
| correct followups turn3 on | 12/12 | 1/12 | 1/12 |
| wrong but completed | 0 | 5 | 11 |
| wrong and visibly failed | 0 | 6 | 0 |

## Turn by turn

| # | User says | control | amnesiac | graceful |
|---|---|---|---|---|
| 1 | Hi! I'm putting together some notes on the Nordic countries. | – | – | – |
| 2 | What's the combined population of Norway and Denmark? | ✅ completed | ✅ completed | ✅ completed |
| 3 | Now add Sweden. | ✅ completed | ❌ completed | ❌ completed |
| 4 | Thanks, that's really helpful. | – | – | – |
| 5 | Which of those is the largest? | ✅ completed | ❌ working ⚠️ error | ❌ completed |
| 6 | Remove Denmark and recompute. | ✅ completed | ❌ working ⚠️ error | ❌ completed |
| 7 | What share of that is Norway? | ✅ completed | ❌ working ⚠️ error | ❌ completed |
| 8 | Add the remaining Nordic country. | ✅ input_required | ✅ input_required | ✅ input_required |
| 9 | Finland | ✅ completed | ❌ completed | ❌ completed |
| 10 | Interesting. Is it cold there this time of year? | – | – | – |
| 11 | How does the total now compare with the very first total I asked about? | ✅ completed | ❌ working ⚠️ error | ❌ completed |
| 12 | List the populations we're working with. | ✅ completed | ❌ completed | ❌ completed |
| 13 | Add Iceland as well. | ✅ completed | ❌ completed | ❌ completed |
| 14 | Which is the smallest now? | ✅ completed | ❌ working ⚠️ error | ❌ completed |
| 15 | Drop Iceland and Finland, and add Denmark back. | ✅ completed | ❌ completed | ❌ completed |
| 16 | Is that the same as an earlier total? | ✅ completed | ❌ working ⚠️ error | ❌ completed |
| 17 | Great, that's all for today. Thanks! | – | – | – |

## What Agent 1 was told (no-memory versions)

| # | User says | amnesiac replied | graceful replied |
|---|---|---|---|
| 2 | What's the combined population of Norway and Denmark? | Norway 5,550,000; Denmark 5,960,000. Combined: 11,510,000. Shares: Norway 48.2%, Denmark 5 | Norway 5,550,000; Denmark 5,960,000. Combined: 11,510,000. Shares: Norway 48.2%, Denmark 5 |
| 3 | Now add Sweden. | Sweden 10,550,000. Combined: 10,550,000. Shares: Sweden 100.0%. | Sweden 10,550,000. Combined: 10,550,000. Shares: Sweden 100.0%. |
| 5 | Which of those is the largest? | (nothing: InternalError: max() iterable argument is empty) | I don't have enough information to work that out. |
| 6 | Remove Denmark and recompute. | (nothing: InternalError: could not convert string to float: 'error: invalid syntax (<unkno | I don't have enough information to work that out. |
| 7 | What share of that is Norway? | (nothing: InternalError: list index out of range) | I don't have enough information to work that out. |
| 8 | Add the remaining Nordic country. | Which country do you mean: Norway, Denmark, Sweden, Finland or Iceland? | Which country do you mean: Norway, Denmark, Sweden, Finland or Iceland? |
| 9 | Finland | I can only help with population figures for Nordic countries. | I can only help with population figures for Nordic countries. |
| 11 | How does the total now compare with the very first total I asked about? | (nothing: InternalError: list index out of range) | I don't have enough information to work that out. |
| 12 | List the populations we're working with. | . | . |
| 13 | Add Iceland as well. | Iceland 390,000. Combined: 390,000. Shares: Iceland 100.0%. | Iceland 390,000. Combined: 390,000. Shares: Iceland 100.0%. |
| 14 | Which is the smallest now? | (nothing: InternalError: min() iterable argument is empty) | I don't have enough information to work that out. |
| 15 | Drop Iceland and Finland, and add Denmark back. | Denmark 5,960,000. Combined: 5,960,000. Shares: Denmark 100.0%. | Denmark 5,960,000. Combined: 5,960,000. Shares: Denmark 100.0%. |
| 16 | Is that the same as an earlier total? | (nothing: InternalError: list index out of range) | I don't have enough information to work that out. |
