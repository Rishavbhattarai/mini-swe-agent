"""Prompted tool-call fallback for models/setups where Ollama's native
function-calling is unavailable or unreliable (common with smaller local
models). The model is instructed to emit exactly one fenced JSON block of the
form:

```tool_call
{"name": "open_file", "arguments": {"path": "foo.py", "line": 10}}
```

which is parsed here instead of relying on message.tool_calls.
"""
from __future__ import annotations

import json
import re

from mini_swe_agent.llm.base import ToolCall

_OPEN_MARKER_RE = re.compile(r"```tool_call\s*")

FALLBACK_INSTRUCTIONS = """
When you want to call a tool, respond with EXACTLY one fenced block in this form
and nothing else:

```tool_call
{"name": "<tool_name>", "arguments": {"<arg>": "<value>"}}
```
"""


def _extract_balanced_json(text: str) -> str | None:
    """Scans forward from the first '{' and returns the substring up to its
    matching closing brace, respecting string literals/escapes. Used instead
    of a regex that requires a closing ``` fence -- confirmed necessary via a
    live run where qwen2.5-coder:7b consistently omitted the closing fence
    after the JSON object, causing every one of 37 consecutive correct tool
    calls in a row to fail parsing and get silently dropped."""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_tool_call(content: str) -> ToolCall | None:
    marker = _OPEN_MARKER_RE.search(content)
    if marker is None:
        return None
    json_str = _extract_balanced_json(content[marker.end() :])
    if json_str is None:
        return None
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        return None
    name = parsed.get("name")
    if not name:
        return None
    return ToolCall(name=name, arguments=parsed.get("arguments", {}))
