"""Extracts a tool call from a model response: native Ollama tool_calls first,
falling back to prompted fenced-JSON parsing when unavailable/unreliable."""
from __future__ import annotations

from mini_swe_agent.llm.base import LLMResponse, ToolCall
from mini_swe_agent.llm.structured_fallback import parse_tool_call


def extract_tool_call(response: LLMResponse, tool_call_mode: str) -> ToolCall | None:
    if tool_call_mode in ("native", "auto") and response.tool_calls:
        return response.tool_calls[0]
    if tool_call_mode in ("prompted", "auto"):
        return parse_tool_call(response.content)
    return None
