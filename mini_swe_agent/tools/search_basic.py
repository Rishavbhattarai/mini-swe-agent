"""Ablation baseline: plain grep search (no ranking, no snippet grouping)."""
from __future__ import annotations

from dataclasses import dataclass

from mini_swe_agent.tools.base import Executor, ToolResult

MAX_LINES = 100


@dataclass
class BasicSearchTool:
    executor: Executor
    name: str = "search"
    description: str = "Search for a literal string or regex across files (plain grep, unranked)."

    @property
    def json_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "file_pattern": {"type": "string", "description": "Optional glob to restrict search, e.g. '*.py'"},
                },
                "required": ["query"],
            },
        }

    def __call__(self, query: str, path: str = ".", file_pattern: str | None = None) -> ToolResult:
        include = f"--include='{file_pattern}'" if file_pattern else ""
        cmd = f"grep -rn {include} -- '{query}' {path}"
        stdout, stderr, code = self.executor.run(cmd)
        if code not in (0, 1):  # grep returns 1 when no matches, not an error
            return ToolResult(success=False, output="", error=stderr or f"grep exited with {code}")
        lines = stdout.splitlines()
        truncated = len(lines) > MAX_LINES
        output = "\n".join(lines[:MAX_LINES])
        if truncated:
            output += f"\n... truncated to first {MAX_LINES} matches"
        if not lines:
            output = "No matches found."
        return ToolResult(success=True, output=output, metadata={"match_count": len(lines), "truncated": truncated})
