"""Shared plumbing for every experiment: run folders, JSONL logs, the raw-HTTP
recorder, and starting Agent 2's server in the background."""

from __future__ import annotations

import json
import socket
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import httpx
import uvicorn
from google.protobuf.json_format import MessageToDict

RUNS_ROOT = Path("runs")


def new_run_dir(experiment_id: str, label: str) -> Path:
    """runs/<experiment_id>/<timestamp>-<label>/"""
    out = RUNS_ROOT / experiment_id / f"{datetime.now():%Y%m%d-%H%M%S}-{label}"
    out.mkdir(parents=True)
    return out


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def to_dict(msg) -> dict[str, Any]:
    """Protobuf A2A object -> plain dict (snake_case field names)."""
    return MessageToDict(msg, preserving_proto_field_name=True)


class TeeTransport(httpx.AsyncBaseTransport):
    """Wraps the real HTTP transport and records every byte on the wire.

    Set `.label` (e.g. the current user turn) to tag the records.
    """

    def __init__(self, path: Path) -> None:
        self.inner = httpx.AsyncHTTPTransport()
        self.path = path
        self.label: Any = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        label = self.label
        append_jsonl(self.path, {"t": time.time(), "label": label, "dir": "out", "method": request.method,
                                 "url": str(request.url), "bytes": len(request.content),
                                 "body": request.content.decode(errors="replace")})
        resp = await self.inner.handle_async_request(request)
        path = self.path

        class Stream(httpx.AsyncByteStream):
            async def __aiter__(self):
                async for chunk in resp.stream:
                    append_jsonl(path, {"t": time.time(), "label": label, "dir": "in", "bytes": len(chunk),
                                        "body": chunk.decode(errors="replace")})
                    yield chunk

            async def aclose(self):
                await resp.aclose()

        return httpx.Response(resp.status_code, headers=resp.headers, stream=Stream(),
                              extensions=resp.extensions, request=request)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def serve(app_factory) -> Iterator[str]:
    """Pick a free local port, build the app with `app_factory(url)`, run it in a
    background thread, and yield its URL."""
    port = free_port()
    app = app_factory(f"http://127.0.0.1:{port}")
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
