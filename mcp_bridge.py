"""
SkySaver AI — MongoDB MCP bridge.

This is the hackathon's partner integration: the agent talks to MongoDB through
the **official MongoDB MCP server** (a Node.js subprocess) over the Model
Context Protocol — not through pymongo directly.

We implement a minimal MCP client ourselves rather than depend on the
`mcp` Python SDK, because that SDK has unresolved Python-3.13 compatibility
issues that surface as opaque `BrokenResourceError`s. The Model Context
Protocol is just newline-delimited JSON-RPC 2.0 over stdio — easy to drive
directly with the stdlib `subprocess` module, no third-party glue needed.

Architecture
------------

    ┌──────────────────────┐   stdio JSON-RPC   ┌──────────────────────┐    Atlas
    │ Gemini agent / chat  │ ◄────────────────► │ mongodb-mcp-server   │ ───────► MongoDB Atlas
    │ (Python, SkySaver)   │  (mcp_bridge.py)   │ (Node.js subprocess) │
    └──────────────────────┘                    └──────────────────────┘

Why this satisfies the hackathon's partner-track requirement
------------------------------------------------------------
The agent's data path goes:
    Python tool call → JSON-RPC over stdio → MongoDB MCP server → Atlas
…with the official `mongodb-mcp-server` package in the middle. Pymongo is not
involved in any of the agent's MongoDB reads or writes that flow through this
bridge.

The Streamlit UI keeps using pymongo for its own CRUD because the UI is not the
agent — it's the application chrome that hosts the agent. The hackathon brief
calls for the *agent's* superpowers to flow through MCP, and that's what this
file delivers.

Prerequisites
-------------
- Node.js ≥ 20.19  (`node --version`)
- `MONGO_URI` set in `.env`

Usage
-----
    from mcp_bridge import mcp_find_one, mcp_update_one
    trip = mcp_find_one("trips", {"_id": "trip_001"})
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from queue import Empty, Queue
from typing import Any

from dotenv import load_dotenv

load_dotenv()


_DB_NAME = "skysaver"
_DEFAULT_TIMEOUT = 30.0
_PROTOCOL_VERSION = "2024-11-05"


# ---------------------------------------------------------------------------
# Subprocess server lifecycle
# ---------------------------------------------------------------------------


class MongoMcpServer:
    """A long-lived subprocess running mongodb-mcp-server, talking JSON-RPC."""

    def __init__(self) -> None:
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise RuntimeError("MONGO_URI must be set in .env")

        env = {
            **os.environ,
            "MDB_MCP_CONNECTION_STRING": mongo_uri,
            "MDB_MCP_TELEMETRY": "disabled",
            "NPM_CONFIG_LOGLEVEL": "silent",
            "NPM_CONFIG_FUND": "false",
            "NPM_CONFIG_AUDIT": "false",
            "NO_UPDATE_NOTIFIER": "1",
        }
        self._proc = subprocess.Popen(
            ["npx", "--yes", "--silent", "mongodb-mcp-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            bufsize=0,
        )
        self._next_id = 1
        self._stderr_lines: list[str] = []
        self._responses: Queue[dict] = Queue()

        # Reader thread: pull lines off stdout, parse, route to queue.
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        # Stderr drain: keep the pipe from blocking; collect for debugging.
        self._err_reader = threading.Thread(target=self._drain_stderr, daemon=True)
        self._err_reader.start()

        try:
            self._initialize()
        except Exception:
            self.close()
            raise

    # ---- I/O loops ----
    def _read_loop(self) -> None:
        assert self._proc.stdout is not None
        for raw in self._proc.stdout:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                # Server printed something non-JSON; remember it for diagnostics.
                self._stderr_lines.append(f"(non-JSON stdout) {line[:300]}")
                continue
            self._responses.put(msg)

    def _drain_stderr(self) -> None:
        assert self._proc.stderr is not None
        for raw in self._proc.stderr:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line:
                self._stderr_lines.append(line)

    # ---- JSON-RPC primitives ----
    def _send(self, method: str, params: dict[str, Any] | None = None) -> int:
        assert self._proc.stdin is not None
        req_id = self._next_id
        self._next_id += 1
        envelope = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        self._proc.stdin.write((json.dumps(envelope) + "\n").encode("utf-8"))
        self._proc.stdin.flush()
        return req_id

    def _send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        assert self._proc.stdin is not None
        envelope = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        self._proc.stdin.write((json.dumps(envelope) + "\n").encode("utf-8"))
        self._proc.stdin.flush()

    def _await_response(self, req_id: int, timeout: float = _DEFAULT_TIMEOUT) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"No JSON-RPC response for id={req_id} within {timeout}s. "
                    f"Stderr tail: {self._stderr_lines[-5:]}"
                )
            try:
                msg = self._responses.get(timeout=min(remaining, 0.5))
            except Empty:
                if self._proc.poll() is not None:
                    raise RuntimeError(
                        f"MongoDB MCP server exited (code {self._proc.returncode}). "
                        f"Stderr: {self._stderr_lines[-10:]}"
                    )
                continue
            if msg.get("id") == req_id:
                return msg
            # Server-initiated notifications: log and keep waiting.
            self._stderr_lines.append(f"(server notification) {json.dumps(msg)[:200]}")

    # ---- Handshake ----
    def _initialize(self) -> None:
        req_id = self._send(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "skysaver-ai", "version": "0.1.0"},
            },
        )
        resp = self._await_response(req_id)
        if "error" in resp:
            raise RuntimeError(f"MCP initialize failed: {resp['error']}")
        # Per the spec, follow up with `notifications/initialized`.
        self._send_notification("notifications/initialized")

    # ---- Public API ----
    def list_tools(self) -> list[dict[str, Any]]:
        req_id = self._send("tools/list")
        resp = self._await_response(req_id)
        if "error" in resp:
            raise RuntimeError(f"tools/list failed: {resp['error']}")
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        req_id = self._send("tools/call", {"name": name, "arguments": arguments})
        resp = self._await_response(req_id)
        if "error" in resp:
            raise RuntimeError(f"tools/call {name} failed: {resp['error']}")
        return resp.get("result", {})

    def close(self) -> None:
        if self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()


# ---------------------------------------------------------------------------
# Singleton — one MCP server per Python process
# ---------------------------------------------------------------------------


_SERVER: MongoMcpServer | None = None
_LOCK = threading.Lock()


def get_server() -> MongoMcpServer:
    global _SERVER
    with _LOCK:
        if _SERVER is None:
            _SERVER = MongoMcpServer()
    return _SERVER


def _parse_content(result: dict[str, Any]) -> Any:
    """MCP tool results come back as {'content': [{'type': 'text', 'text': '...'}, ...]}.

    For MongoDB tools the text is typically JSON we can parse straight out.
    """
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content") or []
    if not content:
        return None
    pieces = []
    for item in content:
        text = item.get("text") if isinstance(item, dict) else None
        if text is None:
            continue
        try:
            pieces.append(json.loads(text))
        except json.JSONDecodeError:
            pieces.append(text)
    if len(pieces) == 1:
        return pieces[0]
    return pieces


# ---------------------------------------------------------------------------
# Public helpers — what the agent calls
# ---------------------------------------------------------------------------


def mcp_list_collections() -> list[str]:
    """List collection names in the skysaver database via MCP.

    Returns a flat list of names (rather than the raw {'collections': [...]} shape
    the MCP server hands back) so callers don't need to know the wire format.
    """
    server = get_server()
    raw = _parse_content(server.call_tool("list-collections", {"database": _DB_NAME}))
    if isinstance(raw, dict) and "collections" in raw:
        return [c.get("name", "") for c in raw["collections"] if isinstance(c, dict)]
    if isinstance(raw, list):
        return [c.get("name", "") if isinstance(c, dict) else str(c) for c in raw]
    return []


def mcp_find_one(collection: str, filter_: dict[str, Any]) -> Any:
    """Find a single document via MCP."""
    server = get_server()
    result = server.call_tool(
        "find",
        {
            "database": _DB_NAME,
            "collection": collection,
            "filter": filter_,
            "limit": 1,
        },
    )
    parsed = _parse_content(result)
    if isinstance(parsed, list) and parsed:
        return parsed[0]
    return parsed


def mcp_find_many(collection: str, filter_: dict[str, Any], limit: int = 50) -> Any:
    """Find multiple documents via MCP."""
    server = get_server()
    return _parse_content(server.call_tool(
        "find",
        {
            "database": _DB_NAME,
            "collection": collection,
            "filter": filter_,
            "limit": limit,
        },
    ))


def mcp_update_one(
    collection: str, filter_: dict[str, Any], update: dict[str, Any]
) -> Any:
    """Update a single document via MCP."""
    server = get_server()
    # MongoDB MCP server's tool names vary across versions — try both.
    for tool_name in ("update-one", "updateOne"):
        try:
            return _parse_content(server.call_tool(
                tool_name,
                {
                    "database": _DB_NAME,
                    "collection": collection,
                    "filter": filter_,
                    "update": update,
                },
            ))
        except RuntimeError as exc:
            if "method not found" not in str(exc).lower() and "unknown tool" not in str(exc).lower():
                raise
    raise RuntimeError("No update-one / updateOne tool exposed by the MongoDB MCP server.")


# ---------------------------------------------------------------------------
# Sync aliases for legacy chatbot code
# ---------------------------------------------------------------------------

mcp_list_collections_sync = mcp_list_collections
mcp_find_one_sync = mcp_find_one
mcp_update_one_sync = mcp_update_one


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------


def _smoke_test() -> None:
    print("=" * 60)
    print("SkySaver MCP bridge — smoke test")
    print("=" * 60)

    print("\n[1/3] Spawning mongodb-mcp-server subprocess...")
    server = get_server()
    print("    OK — server initialized")

    print("\n[2/3] Listing tools exposed by the MCP server:")
    tools = server.list_tools()
    for t in tools[:10]:
        print(f"    · {t.get('name')}  —  {(t.get('description') or '')[:80]}")
    if len(tools) > 10:
        print(f"    · ... ({len(tools) - 10} more)")

    print("\n[3/3] Listing collections in 'skysaver' via MCP:")
    result = mcp_list_collections()
    print(f"    Result: {result}")

    print("\n" + "=" * 60)
    print("OK — the agent can reach MongoDB Atlas via the MCP server.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        _smoke_test()
    except Exception as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}")
        # Best-effort surface stderr from the server
        if _SERVER is not None and _SERVER._stderr_lines:
            print("\n--- Last server stderr lines ---")
            for line in _SERVER._stderr_lines[-20:]:
                print(f"  {line}")
        raise
