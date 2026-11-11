"""Agent 2: an A2A server wrapping a reasoning loop ("reasoner").

Exposure is OPAQUE: the loop runs internally, and only these leave the agent:
  * the final answer (as an artifact, then task "completed"), or
  * a clarifying question (task "input-required" with a message), after which
    Agent 1 can resume the same task by replying with its taskId.

Everything the loop does is written to ground_truth.jsonl.

A reasoner is any object with:
    async def run(context_id, user_text, task_id=None) -> AsyncIterator[step dict]
where each step has "kind" in: thinking | text | tool_call | tool_result |
replay | input_required | final.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

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

from .recording import append_jsonl


class ReasoningAgentExecutor(AgentExecutor):
    def __init__(self, reasoner: Any, ground_truth_path: Path) -> None:
        self.reasoner = reasoner
        self.gt_path = ground_truth_path

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id, context_id = context.task_id, context.context_id
        user_text = context.get_user_input()
        append_jsonl(self.gt_path, {"t": time.time(), "context_id": context_id, "task_id": task_id,
                                    "kind": "input", "content": user_text,
                                    "resumed_task": context.current_task is not None})
        if context.current_task is None:
            await event_queue.enqueue_event(
                new_task(task_id, context_id, TaskState.TASK_STATE_SUBMITTED, history=[context.message])
            )
        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.start_work()

        seq = 0
        async for step in self.reasoner.run(context_id, user_text, task_id=task_id):
            seq += 1
            append_jsonl(self.gt_path, {"t": time.time(), "context_id": context_id, "task_id": task_id,
                                        "seq": seq, **step})
            if step["kind"] == "input_required":
                await updater.requires_input(updater.new_agent_message([new_text_part(step["content"])]))
                return  # yield control; Agent 1 resumes by replying with this taskId
            if step["kind"] == "final":
                await updater.add_artifact([new_text_part(step["content"])], name="answer")
                await updater.complete()
                return
            # OPAQUE: every other step stays inside Agent 2.
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()


def build_app(url: str, reasoner: Any, ground_truth_path: Path,
              name: str = "Nordic Stats Agent",
              description: str = "Looks up Nordic population figures and does the arithmetic.") -> Starlette:
    card = AgentCard(
        name=name,
        description=description,
        version="0.2.0",
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", url=url, protocol_version="1.0")],
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[AgentSkill(id="population", name="Population maths",
                           description="Combined populations and shares", tags=["stats"])],
    )
    handler = DefaultRequestHandler(
        agent_executor=ReasoningAgentExecutor(reasoner, ground_truth_path),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = create_agent_card_routes(card) + create_jsonrpc_routes(handler, rpc_url="/")
    return Starlette(routes=routes)
