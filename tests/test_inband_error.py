"""Regression test for the proxy artefact found on 7 Sep 2026: a gateway that has
already sent HTTP 200 and some content can only report a failure as an in-band
SSE error event. The shared client must treat that as an error, never as a
successful (truncated) answer.

    python tests/test_inband_error.py
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from failoverbench.adapters.http_common import call_chat  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def sse(obj) -> bytes:
    data = f"data: {json.dumps(obj)}\n\n".encode()
    return f"{len(data):x}\r\n".encode() + data + b"\r\n"


async def gateway_like(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Answers any POST like a gateway whose upstream died after two tokens."""
    head = await reader.readuntil(b"\r\n\r\n")
    length = 0
    for ln in head.decode("latin-1").split("\r\n"):
        if ln.lower().startswith("content-length:"):
            length = int(ln.split(":", 1)[1])
    if length:
        await reader.readexactly(length)
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n")
    chunk = lambda delta: {"id": "x", "object": "chat.completion.chunk", "model": "fb-s08-stream-cut",  # noqa: E731
                           "choices": [{"index": 0, "delta": delta, "finish_reason": None}]}
    writer.write(sse(chunk({"role": "assistant", "content": ""})))
    writer.write(sse(chunk({"content": "A"})))
    writer.write(sse(chunk({"content": " gateway"})))
    writer.write(sse({"error": {"message": "litellm.APIConnectionError: peer closed connection", "code": "500"}}))
    writer.write(b"0\r\n\r\n")
    await writer.drain()
    writer.close()


async def _run():
    port = free_port()
    server = await asyncio.start_server(gateway_like, "127.0.0.1", port)
    try:
        async with httpx.AsyncClient() as client:
            r = await call_chat(client, f"http://127.0.0.1:{port}/v1", "fb-s08-stream-cut",
                                [{"role": "user", "content": "hi"}], stream=True, timeout=10.0)
    finally:
        server.close()
        await server.wait_closed()
    return r


def test_inband_error_event_is_an_error_not_a_truncated_success():
    r = asyncio.run(_run())
    assert r.ok is False, r
    assert "in-band error event" in (r.error or ""), r.error
    assert r.content == "A gateway", r.content   # what arrived before the error is kept for the record
    assert r.chunks == 3, r.chunks


if __name__ == "__main__":
    test_inband_error_event_is_an_error_not_a_truncated_success()
    print("ok  test_inband_error_event_is_an_error_not_a_truncated_success")
