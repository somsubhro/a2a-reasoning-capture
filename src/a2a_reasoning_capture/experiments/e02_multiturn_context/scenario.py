"""The scripted user's 17-turn conversation with Agent 1.

route  : "self"   -> Agent 1 answers on its own (small talk), no A2A call
         "agent2" -> Agent 1 delegates to Agent 2 over A2A
expect : text that must appear in the reply for the turn to count as correct
         (for the clarification turn: text that must appear in Agent 2's question)
needs  : which earlier turns this one depends on (for the write-up)
"""

TURNS = [
    {"text": "Hi! I'm putting together some notes on the Nordic countries.",
     "route": "self", "self_reply": "Happy to help. Ask me anything about Nordic populations."},
    {"text": "What's the combined population of Norway and Denmark?",
     "route": "agent2", "expect": "11,510,000", "needs": []},
    {"text": "Now add Sweden.",
     "route": "agent2", "expect": "22,060,000", "needs": [2]},
    {"text": "Thanks, that's really helpful.",
     "route": "self", "self_reply": "Glad it helps!"},
    {"text": "Which of those is the largest?",
     "route": "agent2", "expect": "Sweden", "needs": [2, 3]},
    {"text": "Remove Denmark and recompute.",
     "route": "agent2", "expect": "16,100,000", "needs": [2, 3]},
    {"text": "What share of that is Norway?",
     "route": "agent2", "expect": "34.5%", "needs": [6]},
    {"text": "Add the remaining Nordic country.",
     "route": "agent2", "expect": "Finland", "clarification": True, "needs": [6]},
    {"text": "Finland",
     "route": "agent2", "expect": "21,700,000", "needs": [8]},
    {"text": "Interesting. Is it cold there this time of year?",
     "route": "self", "self_reply": "Very! Winters are long up there."},
    {"text": "How does the total now compare with the very first total I asked about?",
     "route": "agent2", "expect": "10,190,000", "needs": [2, 9]},
    {"text": "List the populations we're working with.",
     "route": "agent2", "expect": "Finland 5,600,000", "needs": [9]},
    {"text": "Add Iceland as well.",
     "route": "agent2", "expect": "22,090,000", "needs": [9]},
    {"text": "Which is the smallest now?",
     "route": "agent2", "expect": "Iceland", "needs": [13]},
    {"text": "Drop Iceland and Finland, and add Denmark back.",
     "route": "agent2", "expect": "22,060,000", "needs": [13]},
    {"text": "Is that the same as an earlier total?",
     "route": "agent2", "expect": "Yes", "needs": [3, 15]},
    {"text": "Great, that's all for today. Thanks!",
     "route": "self", "self_reply": "Anytime. Good luck with the notes!"},
]
