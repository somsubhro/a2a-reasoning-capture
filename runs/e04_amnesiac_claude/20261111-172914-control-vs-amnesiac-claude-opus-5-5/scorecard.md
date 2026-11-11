# e04 scorecard: amnesiac Agent 2 with a real model

Run folder: `runs/e04_amnesiac_claude/20261111-172914-control-vs-amnesiac-claude-opus-5-5`  ·  e02's 17-turn conversation, stateful strategy  ·  one run

| Agent 2 version | What it is |
|---|---|
| control | Claude Opus 5.5, history kept per contextId |
| amnesiac | Claude Opus 5.5, blank history on every call |

## Protocol health, correctness and cost

| Metric | control | amnesiac |
|---|---|---|
| a2a calls | 13 | 15 |
| contexts used | 1 | 1 |
| every call got task id | True | True |
| tasks completed | 12 | 4 |
| tasks input required | 1 | 11 |
| tasks failed | 0 | 0 |
| client side errors | 0 | 0 |
| tasks still open at end | 0 | 0 |
| correct answers | 12/13 | 1/13 |
| correct followups turn3 on | 11/12 | 0/12 |
| wrong but completed | 1 | 1 |
| wrong and visibly failed | 0 | 11 |
| model api calls | 23 | 19 |
| input tokens | 61449 | 16582 |
| output tokens | 2867 | 1922 |
| input tokens last turn | 4606 | 825 |
| cost usd | 0.3031 | 0.1048 |
| tool calls | 27 | 18 |
| ask user calls | 1 | 11 |
| latency s total | 42.6 | 52.1 |
| latency s slowest turn | 7.4 | 7.1 |
| models used | claude-opus-5-5 | claude-opus-5-5 |

## Turn by turn

| # | User says | control | control tokens in/out | amnesiac | amnesiac tokens in/out |
|---|---|---|---|---|---|
| 1 | Hi! I'm putting together some notes on the Nordic countries. | – | – | – | – |
| 2 | What's the combined population of Norway and Denmark? | ✅ completed | 3,135 / 344 | ✅ completed | 3,135 / 349 |
| 3 | Now add Sweden. | ✅ completed | 4,633 / 405 | ❌ input_required | 819 / 148 |
| 4 | Thanks, that's really helpful. | – | – | completed | 823 / 83 |
| 5 | Which of those is the largest? | ✅ completed | 1,923 / 41 | ❌ input_required | 820 / 95 |
| 6 | Remove Denmark and recompute. | ✅ completed | 4,228 / 284 | ❌ input_required | 823 / 96 |
| 7 | What share of that is Norway? | ✅ completed | 2,365 / 34 | ❌ input_required | 820 / 92 |
| 8 | Add the remaining Nordic country. | ✅ input_required | 2,415 / 125 | ❌ input_required | 823 / 117 |
| 9 | Finland | ✅ completed | 8,179 / 458 | ❌ completed | 2,752 / 247 |
| 10 | Interesting. Is it cold there this time of year? | – | – | – | – |
| 11 | How does the total now compare with the very first total I asked about? | ✅ completed | 6,515 / 190 | ❌ input_required | 828 / 112 |
| 12 | List the populations we're working with. | ❌ completed | 3,432 / 96 | ❌ input_required | 820 / 108 |
| 13 | Add Iceland as well. | ✅ completed | 11,279 / 618 | ❌ input_required | 820 / 117 |
| 14 | Which is the smallest now? | ✅ completed | 4,339 / 37 | ❌ input_required | 820 / 90 |
| 15 | Drop Iceland and Finland, and add Denmark back. | ✅ completed | 4,400 / 190 | ❌ input_required | 831 / 140 |
| 16 | Is that the same as an earlier total? | ✅ completed | 4,606 / 45 | ❌ input_required | 823 / 103 |
| 17 | Great, that's all for today. Thanks! | – | – | completed | 825 / 25 |

## What Agent 1 was told

**2. What's the combined population of Norway and Denmark?**
- *control* (✅ completed): Norway and Denmark have a combined population of 11,510,000 (2024 estimates). Norway has 5,550,000 people (48.2%) and Denmark has 5,960,000 (51.8%).
- *amnesiac* (✅ completed): Norway and Denmark have a combined population of 11,510,000, based on 2024 estimates. Norway has 5,550,000 people (48.2% of the total) and Denmark has 5,960,000 (51.8%).

**3. Now add Sweden.**
- *control* (✅ completed): With Sweden added, the combined population is 22,060,000 (2024 estimates). Norway has 5,550,000 (25.2%), Denmark 5,960,000 (27.0%) and Sweden 10,550,000 (47.8%).
- *amnesiac* (❌ input_required): I don't have a working set of countries yet. Which countries should Sweden be added to?

**5. Which of those is the largest?**
- *control* (✅ completed): Sweden is the largest, with 10,550,000 people, or 47.8% of the three-country total of 22,060,000.
- *amnesiac* (❌ input_required): Which countries do you mean by "those"? No working set has been established yet.

**6. Remove Denmark and recompute.**
- *control* (✅ completed): Without Denmark, Norway and Sweden have a combined population of 16,100,000 (2024 estimates). Norway has 5,550,000 (34.5%) and Sweden 10,550,000 (65.5%).
- *amnesiac* (❌ input_required): There's no working set of countries yet. Which countries should I start from before removing Denmark?

**7. What share of that is Norway?**
- *control* (✅ completed): Norway makes up 34.5% of the 16,100,000 total, with 5,550,000 people.
- *amnesiac* (❌ input_required): Norway's share of what total? Which countries should be in the working set?

**8. Add the remaining Nordic country.**
- *control* (✅ input_required): Denmark, Finland and Iceland aren't in the set yet, so which one should I add?
- *amnesiac* (❌ input_required): There's no working set yet, so which countries are already in it (and so which one is "remaining")?

**9. Finland**
- *control* (✅ completed): You confirmed Finland, so Norway, Sweden and Finland now have a combined population of 21,700,000 (2024 estimates). Norway has 5,550,000 (25.6%), Sweden 10,550,000 (48.6%) and Finland 5,600,000 (25.8%).
- *amnesiac* (❌ completed): Your working set is now just Finland, with a population of 5,600,000 (2024 estimate). That's also the combined total, so Finland's share is 100.0%.

**11. How does the total now compare with the very first total I asked about?**
- *control* (✅ completed): The current total of 21,700,000 for Norway, Sweden and Finland is 10,190,000 higher than your first total of 11,510,000 for Norway and Denmark. That's an increase of 88.5%.
- *amnesiac* (❌ input_required): I don't have any earlier totals from this conversation. Which countries were in your first total, and which are in your current set?

**12. List the populations we're working with.**
- *control* (❌ completed): The current set is Norway with 5,550,000, Sweden with 10,550,000 and Finland with 5,600,000 (2024 estimates), for a total of 21,700,000.
- *amnesiac* (❌ input_required): Which Nordic countries should be in the working set (Norway, Denmark, Sweden, Finland, Iceland)?

**13. Add Iceland as well.**
- *control* (✅ completed): With Iceland added, Norway, Sweden, Finland and Iceland have a combined population of 22,090,000 (2024 estimates). Norway has 5,550,000 (25.1%), Sweden 10,550,000 (47.8%), Finland 5,600,000 (25.4%) and Iceland 390,000 (1.8%).
- *amnesiac* (❌ input_required): I don't have a working set of countries yet. Which countries should Iceland be added to?

**14. Which is the smallest now?**
- *control* (✅ completed): Iceland is the smallest, with 390,000 people, or 1.8% of the 22,090,000 total.
- *amnesiac* (❌ input_required): Which countries are in your working set? I don't have any selected yet.

**15. Drop Iceland and Finland, and add Denmark back.**
- *control* (✅ completed): Norway, Sweden and Denmark have a combined population of 22,060,000 (2024 estimates), the same set and total as earlier. Norway has 5,550,000 (25.2%), Sweden 10,550,000 (47.8%) and Denmark 5,960,000 (27.0%).
- *amnesiac* (❌ input_required): I don't have a working set yet. Which countries are in it right now, before dropping Iceland and Finland and adding Denmark?

**16. Is that the same as an earlier total?**
- *control* (✅ completed): Yes, it matches the 22,060,000 total from when you added Sweden to Norway and Denmark, because it's the same three countries.
- *amnesiac* (❌ input_required): There's no earlier total in our conversation yet. Which countries' total should I compare, and what should I compare it with?

