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

_BLOCK_RE = re.compile(r"```tool_call\s*(\{.*?\})\s*```", re.DOTALL)

FALLBACK_INSTRUCTIONS = """
When you want to call a tool, respond with EXACTLY one fenced block in this form
and nothing else:

```tool_call
{"name": "<tool_name>", "arguments": {"<arg>": "<value>"}}
```
"""


def parse_tool_call(content: str) -> ToolCall | None:
    match = _BLOCK_RE.search(content)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    name = parsed.get("name")
    if not name:
        return None
    return ToolCall(name=name, arguments=parsed.get("arguments", {}))
