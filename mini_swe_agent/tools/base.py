"""Shared tool contracts: every tool implementation (any ablation variant) returns
a ToolResult and exposes a JSON schema, so the agent loop never needs to know
which concrete implementation is bound behind a given tool name."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Executor(Protocol):
    """Runs a shell command in the current working environment (local clone or
    a docker-exec'd SWE-bench instance container) and returns its output."""

    def run(self, cmd: str, cwd: str | None = None) -> tuple[str, str, int]:
        """Returns (stdout, stderr, exit_code)."""
        ...

    def write_file(self, path: str, content: str) -> bool:
        """Overwrites `path` with `content`. Returns True on success."""
        ...


class Tool(Protocol):
    name: str
    description: str

    @property
    def json_schema(self) -> dict[str, Any]:
        """OpenAI/Ollama-style function schema: {name, description, parameters}."""
        ...

    def __call__(self, **kwargs: Any) -> ToolResult: ...


class ToolRegistry:
    def __init__(self, tools: dict[str, Tool]):
        self._tools = tools

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def get_openai_style_schema(self) -> list[dict[str, Any]]:
        return [
            {"type": "function", "function": tool.json_schema}
            for tool in self._tools.values()
        ]

    def get_prompt_block(self) -> str:
        """Text description of every tool, used by the prompted tool-call fallback
        when native function-calling is unavailable or unreliable."""
        lines = []
        for tool in self._tools.values():
            schema = tool.json_schema
            lines.append(f"- {schema['name']}: {schema['description']}")
            lines.append(f"  args schema: {schema['parameters']}")
        return "\n".join(lines)

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        if name not in self._tools:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool '{name}'. Available tools: {self.names()}",
            )
        return self._tools[name](**kwargs)
