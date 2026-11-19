"""A tiny local imitation of the Anthropic Messages API for offline tests.

Plain requests get a canned text answer. Structured-output requests get a reply generated from the JSON schema:
- Ragas with instructor sends the schema inside the system prompt ("json_schema: {...}") and expects JSON text.
- A forced tool call (tools in the request) gets a tool_use block built from the tool's input_schema.
This lets the whole judge path run without network access, an API key or cost.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

CANNED_TEXT = "No. Payment tests must use a mock provider [payment_test_policy.md#test-environment-rules-pt-1-to-pt-3]."


def schema_from_system(system) -> dict | None:
    """Pull the JSON schema that instructor puts after 'json_schema:' in the system prompt, if there is one."""
    text = system if isinstance(system, str) else " ".join(block.get("text", "") for block in system or [])
    marker = text.find("json_schema:")
    if marker < 0:
        return None
    start = text.find("{", marker)
    try:
        schema, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    return schema


def _resolve(schema: dict, defs: dict) -> dict:
    while "$ref" in schema:
        schema = defs[schema["$ref"].split("/")[-1]]
    return schema


def fill(schema: dict, defs: dict):
    schema = _resolve(schema, defs)
    if "anyOf" in schema:
        options = [s for s in schema["anyOf"] if s.get("type") != "null"]
        return fill(options[0], defs) if options else None
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema.get("type")
    if kind == "object":
        return {key: fill(sub, defs) for key, sub in schema.get("properties", {}).items()}
    if kind == "array":
        return [fill(schema.get("items", {"type": "string"}), defs)]
    if kind == "integer":
        return 1
    if kind == "number":
        return 1.0
    if kind == "boolean":
        return True
    return "x"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test output quiet
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append({"path": self.path, "body": body})
        tools = body.get("tools") or []
        json_schema = schema_from_system(body.get("system"))
        if json_schema is not None and not tools:
            content = [{"type": "text", "text": json.dumps(fill(json_schema, json_schema.get("$defs", {})))}]
            stop = "end_turn"
        elif tools:
            tool = tools[0]
            schema = tool["input_schema"]
            content = [{"type": "tool_use", "id": "toolu_mock", "name": tool["name"],
                        "input": fill(schema, schema.get("$defs", {}))}]
            stop = "tool_use"
        else:
            content = [{"type": "text", "text": self.server.canned_text}]
            stop = "end_turn"
        reply = {"id": "msg_mock", "type": "message", "role": "assistant", "model": body.get("model", "mock"),
                 "content": content, "stop_reason": stop, "stop_sequence": None,
                 "usage": {"input_tokens": 10, "output_tokens": 5}}
        data = json.dumps(reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class MockAnthropic:
    """Context manager: with MockAnthropic() as mock: Anthropic(base_url=mock.url, api_key='mock')"""

    def __init__(self, canned_text: str = CANNED_TEXT):
        self.canned_text = canned_text

    def __enter__(self):
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.server.requests = []
        self.server.canned_text = self.canned_text
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.requests = self.server.requests
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
