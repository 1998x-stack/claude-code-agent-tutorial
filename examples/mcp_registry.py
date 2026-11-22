"""Offline MCP multi-server tool catalog and modern request envelope builder.

No transport, credentials, server launch, network or model execution.
Server identity is assigned by the host, not trusted remote serverInfo.
Full JSON Schema validation needs a dedicated standards-compliant library.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any

from mcp_protocol import request

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
SERVER = re.compile(r"^[a-z][a-z0-9-]{0,39}$")


@dataclass(frozen=True)
class RemoteTool:
    server_id: str
    name: str
    schema: dict[str, Any]
    annotations: dict[str, Any]

    @property
    def qualified_name(self) -> str:
        return f"{self.server_id}::{self.name}"


class ToolRegistry:
    def __init__(self):
        self._catalog: dict[str, RemoteTool] = {}

    def add_server_tools(self, server_id: str,
                         pages: tuple[dict[str, Any], ...]) -> None:
        if not SERVER.fullmatch(server_id):
            raise ValueError("server ID must be stable host-assigned identifier")
        if any(k.startswith(server_id + "::") for k in self._catalog):
            raise ValueError("server already registered")
        incoming: dict[str, RemoteTool] = {}
        if not pages:
            raise ValueError("discovery is incomplete")
        for page in pages:
            if page.get("resultType") != "complete" or not isinstance(
                    page.get("tools"), list):
                raise ValueError("invalid modern MCP tools/list result")
            for item in page["tools"]:
                if not isinstance(item, dict):
                    raise ValueError("invalid tool")
                name = item.get("name", "")
                schema = item.get("inputSchema")
                if not isinstance(name, str) or not NAME.fullmatch(name):
                    raise ValueError("invalid tool name")
                if not isinstance(schema, dict) or schema.get("type") != "object":
                    raise ValueError("demo requires object schema")
                q = f"{server_id}::{name}"
                if q in incoming:
                    raise ValueError("duplicate tool in server discovery")
                incoming[q] = RemoteTool(server_id, name, schema,
                                         item.get("annotations") or {})
        self._catalog.update(incoming)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._catalog))

    def prepare_call(self, qualified_name: str, arguments: dict[str, Any],
                     request_id: int, allowed: frozenset[str]) -> dict[str, Any]:
        if qualified_name not in self._catalog or qualified_name not in allowed:
            raise PermissionError("unapproved or unregistered tool")
        tool = self._catalog[qualified_name]
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        schema = tool.schema
        # Teaching subset: exact required keys, no extra fields, simple string/int.
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        if not isinstance(properties, dict) or not isinstance(schema.get("required", []), list):
            raise ValueError("invalid demo schema")
        if not required.issubset(arguments) or not set(arguments).issubset(properties):
            raise ValueError("missing or unexpected arguments")
        for key, value in arguments.items():
            kind = properties[key].get("type")
            if kind == "string" and not isinstance(value, str):
                raise ValueError("expected string")
            if kind == "integer" and type(value) is not int:
                raise ValueError("expected integer")
            if kind not in {"string", "integer"}:
                raise ValueError("unsupported demo schema type")
        # annotations are explicitly NOT used to grant authorization.
        return request("tools/call", request_id, {
            "name": tool.name, "arguments": arguments
        })


if __name__ == "__main__":
    registry = ToolRegistry()
    registry.add_server_tools("docs", ({"resultType": "complete",
        "tools": [{"name": "lookup", "inputSchema": {
            "type": "object", "properties": {"query": {"type": "string"}},
            "required": ["query"]}}]},))
    print(registry.names())
