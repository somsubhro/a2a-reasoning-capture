"""Agent 2 variants for e03. All share e02's conversational agent code."""

from __future__ import annotations

from collections.abc import AsyncIterator

from ..e02_multiturn_context.agent2 import ConversationalStatsAgent


class AmnesiacAgent(ConversationalStatsAgent):
    """e02's Agent 2 with its memory wiped before every call.

    Same code otherwise, so it fails however that code fails when state is
    missing, including raising exceptions.
    """

    name = "amnesiac"

    async def run(self, context_id: str, user_text: str, task_id: str | None = None) -> AsyncIterator[dict]:
        self.memory.clear()  # forget everything, every call
        async for step in super().run(context_id, user_text, task_id=task_id):
            yield step


class GracefulAmnesiacAgent(AmnesiacAgent):
    """No memory, and never crashes: always returns *some* answer.

    Closer to an LLM agent missing context: it doesn't throw, it just does its best.
    """

    name = "graceful-amnesiac"

    async def run(self, context_id: str, user_text: str, task_id: str | None = None) -> AsyncIterator[dict]:
        try:
            async for step in super().run(context_id, user_text, task_id=task_id):
                yield step
        except Exception as e:  # noqa: BLE001
            yield {"kind": "thinking", "content": f"Missing context ({type(e).__name__}); answering anyway."}
            yield {"kind": "final", "content": "I don't have enough information to work that out."}
