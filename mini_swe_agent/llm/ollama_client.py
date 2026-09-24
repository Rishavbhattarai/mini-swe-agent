"""Direct HTTP client against Ollama's /api/chat, deliberately avoiding a hard
dependency on the `ollama` pip package so tool-calling behavior stays fully
inspectable/debuggable (the `ollama` client remains a drop-in optional swap)."""
from __future__ import annotations

from typing import Any

import httpx

from mini_swe_agent.llm.base import LLMResponse, ToolCall


class OllamaClient:
    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        temperature: float = 0.0,
        request_timeout_s: int = 120,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = temperature
        self.timeout = request_timeout_s

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        if tools:
            payload["tools"] = tools

        resp = httpx.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        message = data.get("message", {})
        content = message.get("content", "") or ""
        raw_tool_calls = message.get("tool_calls") or []
        tool_calls = [
            ToolCall(name=tc["function"]["name"], arguments=tc["function"].get("arguments", {}))
            for tc in raw_tool_calls
        ]
        return LLMResponse(content=content, tool_calls=tool_calls, raw=data)
