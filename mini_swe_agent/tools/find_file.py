from __future__ import annotations

from dataclasses import dataclass

from mini_swe_agent.tools.base import Executor, ToolResult

MAX_RESULTS = 50


@dataclass
class FindFileTool:
    executor: Executor
    name: str = "find_file"
    description: str = "Find files by name pattern (glob) under a starting path."

    @property
    def json_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern, e.g. '*.py' or '**/test_*.py'"},
                    "path": {"type": "string", "description": "Directory to search from.", "default": "."},
                },
                "required": ["pattern"],
            },
        }

    def __call__(self, pattern: str, path: str = ".") -> ToolResult:
        cmd = f"find {path} -type f -name '{pattern}'"
        stdout, stderr, code = self.executor.run(cmd)
        if code != 0:
            return ToolResult(success=False, output="", error=stderr or f"find exited with {code}")
        matches = [line for line in stdout.splitlines() if line.strip()]
        truncated = len(matches) > MAX_RESULTS
        matches = matches[:MAX_RESULTS]
        output = "\n".join(matches)
        if truncated:
            output += f"\n... truncated to first {MAX_RESULTS} results"
        return ToolResult(success=True, output=output, metadata={"count": len(matches), "truncated": truncated})
