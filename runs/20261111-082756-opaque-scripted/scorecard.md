# A2A reasoning-capture scorecard: `opaque` mode, `scripted` reasoner

Run folder: `runs/20261111-082756-opaque-scripted`

## By step type

| Step type | Steps in Agent 2's loop | Seen by Agent 1 | % | via stream | via get_task |
|---|---|---|---|---|---|
| thinking | 4 | 0 | 0% | 0 | 0 |
| tool_call | 5 | 0 | 0% | 0 | 0 |
| tool_result | 5 | 0 | 0% | 0 | 0 |
| text | 2 | 0 | 0% | 0 | 0 |
| final | 2 | 2 | 100% | 2 | 2 |

## Overall

| Metric | Value |
|---|---|
| ground truth steps | 18 |
| recovered steps | 2 |
| recovered pct | 11 |
| intermediate steps recovered | 0/16 |
| order preserved for recovered | True |
| min delay ms | 2.1 |
| max delay ms | 4.6 |
| stream events received | 8 |
| wire bytes in | 4926 |
| wire bytes out | 960 |
| same context id both turns | True |
| agent2 remembered turn1 | True |

## Step by step

| Turn task | # | Type | Seen? | Delay ms | Content |
|---|---|---|---|---|---|
| 1 | 1 | thinking | no | – | Turn 1 in context. User asks about ['norway', 'denmark']. I remember from earlie |
| 1 | 2 | tool_call | no | – | {"input": {"query": "population of norway"}, "name": "lookup_fact"} |
| 1 | 3 | tool_result | no | – | {"name": "lookup_fact", "output": "5,550,000 (2024 estimate)"} |
| 1 | 4 | tool_call | no | – | {"input": {"query": "population of denmark"}, "name": "lookup_fact"} |
| 1 | 5 | tool_result | no | – | {"name": "lookup_fact", "output": "5,960,000 (2024 estimate)"} |
| 1 | 6 | thinking | no | – | I now have populations for ['norway', 'denmark']. Summing them and computing eac |
| 1 | 7 | tool_call | no | – | {"input": {"expression": "5550000 + 5960000"}, "name": "calculate"} |
| 1 | 8 | tool_result | no | – | {"name": "calculate", "output": "11510000"} |
| 1 | 9 | text | no | – | Checked the numbers; writing the answer. |
| 1 | 10 | final | yes | 4.6 | Combined population of Norway, Denmark: 11,510,000. Shares: Norway 48.2%, Denmar |
| 2 | 1 | thinking | no | – | Turn 2 in context. User asks about ['sweden']. I remember from earlier turns: [' |
| 2 | 2 | tool_call | no | – | {"input": {"query": "population of sweden"}, "name": "lookup_fact"} |
| 2 | 3 | tool_result | no | – | {"name": "lookup_fact", "output": "10,550,000 (2024 estimate)"} |
| 2 | 4 | thinking | no | – | I now have populations for ['norway', 'denmark', 'sweden']. Summing them and com |
| 2 | 5 | tool_call | no | – | {"input": {"expression": "5550000 + 5960000 + 10550000"}, "name": "calculate"} |
| 2 | 6 | tool_result | no | – | {"name": "calculate", "output": "22060000"} |
| 2 | 7 | text | no | – | Checked the numbers; writing the answer. |
| 2 | 8 | final | yes | 2.1 | Combined population of Norway, Denmark, Sweden: 22,060,000. Shares: Norway 25.2% |
