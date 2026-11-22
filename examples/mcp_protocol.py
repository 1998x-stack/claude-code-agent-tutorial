"""Offline JSON-RPC envelope samples for two MCP protocol eras.

Not a network transport or a complete MCP SDK. Modern per-request metadata
follows spec 2026-07-28. Legacy initialize is only for 2025-11-25 and prior.
"""
from __future__ import annotations
import json
from typing import Any

MODERN_VERSION = "2026-07-28"
LEGACY_VERSION = "2025-11-25"


def request(method: str, request_id: int, params: dict[str, Any] | None = None,
            *, modern: bool = True) -> dict[str, Any]:
    if not method or type(request_id) is not int or request_id < 0:
        raise ValueError("expected method and nonnegative numeric request ID")
    if modern and method in {"initialize", "notifications/initialized"}:
        raise ValueError("initialize is legacy-only")
    body = dict(params or {})
    if modern:
        if "_meta" in body:
            raise ValueError("caller cannot override MCP-required metadata")
        body["_meta"] = {
            "io.modelcontextprotocol/protocolVersion": MODERN_VERSION,
            "io.modelcontextprotocol/clientInfo": {
                "name": "offline-tutorial", "version": "1.0.0"
            },
            "io.modelcontextprotocol/clientCapabilities": {},
        }
    return {"jsonrpc": "2.0", "id": request_id,
            "method": method, "params": body}


def legacy_initialize(request_id: int = 1) -> dict[str, Any]:
    """Legacy handshake; not used by modern 2026-07-28 clients."""
    return request("initialize", request_id, {
        "protocolVersion": LEGACY_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "offline-tutorial", "version": "1.0.0"},
    }, modern=False)


def parse_response(frame: dict[str, Any], expected_id: int,
                   *, modern: bool = True) -> dict[str, Any]:
    if frame.get("jsonrpc") != "2.0" or frame.get("id") != expected_id:
        raise ValueError("invalid JSON-RPC envelope or mismatched request ID")
    if ("result" in frame) == ("error" in frame):
        raise ValueError("exactly one result or error is required")
    if "error" in frame:
        err = frame["error"]
        if not isinstance(err, dict) or not isinstance(err.get("code"), int):
            raise ValueError("malformed JSON-RPC error")
        raise ValueError(f"JSON-RPC error {err['code']}: {err.get('message', '')}")
    result = frame["result"]
    if not isinstance(result, dict):
        raise ValueError("expected object result in this teaching adapter")
    if modern and result.get("resultType") not in {"complete", "input_required"}:
        raise ValueError("unrecognized modern MCP resultType")
    return result


def stdio_line(message: dict[str, Any]) -> str:
    """Encode one JSON-RPC message per line, no embedded literal newlines."""
    return json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"


if __name__ == "__main__":
    print(stdio_line(request("tools/list", 10, {})), end="")
