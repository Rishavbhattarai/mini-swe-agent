"""Ablation baseline: dump the entire file with line numbers, no cursor/window."""
from __future__ import annotations

from dataclasses import dataclass

from mini_swe_agent.tools.base import Executor, ToolResult


@dataclass
class FullFileOpenTool:
    executor: Executor
    name: str = "open_file"
    description: str = "Open a file and view its full contents with line numbers."

    @property
    def json_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
            },
        }

    def __call__(self, path: str, **_ignored) -> ToolResult:
        stdout, stderr, code = self.executor.run(f"cat -n {path}")
        if code != 0:
            return ToolResult(success=False, output="", error=stderr or f"could not open {path}")
        return ToolResult(success=True, output=stdout, metadata={"path": path})
