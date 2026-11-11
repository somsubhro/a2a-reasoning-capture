"""Agent 2: an A2A server wrapping the reasoning loop.

Baseline exposure = OPAQUE: the loop runs internally, and only the final answer
leaves the agent (as an artifact), which is what most A2A agents do by default.

Everything the loop does is written to ground_truth.jsonl so we can later
measure how much of it Agent 1 was able to see.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from a2a.helpers import new_task, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types.a2a_pb2 import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    TaskState,
)
from starlette.applications import Starlette

from .reasoners import make_reasoner


class ReasoningAgentExecutor(AgentExecutor):
    def __init__(self, reasoner_kind: str, ground_truth_path: Path) -> None:
        self.reasoner = make_reasoner(reasoner_kind)
        self.gt_path = ground_truth_path

    def _log(self, record: dict) -> None:
        with self.gt_path.open("a") as f:
            f.write(json.dumps(record) + "\n")

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id, context_id = context.task_id, context.context_id
        if context.current_task is None:
            await event_queue.enqueue_event(
                new_task(task_id, context_id, TaskState.TASK_STATE_SUBMITTED, history=[context.message])
            )
        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.start_work()

        final_text = ""
        seq = 0
        async for step in self.reasoner.run(context_id, context.get_user_input()):
            seq += 1
            self._log({"t": time.time(), "context_id": context_id, "task_id": task_id, "seq": seq, **step})
            if step["kind"] == "final":
                final_text = step["content"]
            # OPAQUE: intermediate steps are NOT sent to Agent 1.

        await updater.add_artifact([new_text_part(final_text)], name="answer")
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()


def build_app(url: str, reasoner_kind: str, ground_truth_path: Path) -> Starlette:
    card = AgentCard(
        name="Nordic Stats Agent",
        description="Looks up Nordic population figures and does the arithmetic.",
        version="0.1.0",
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", url=url, protocol_version="1.0")],
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[AgentSkill(id="population", name="Population maths",
                           description="Combined populations and shares", tags=["stats"])],
    )
    handler = DefaultRequestHandler(
        agent_executor=ReasoningAgentExecutor(reasoner_kind, ground_truth_path),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = create_agent_card_routes(card) + create_jsonrpc_routes(handler, rpc_url="/")
    return Starlette(routes=routes)
