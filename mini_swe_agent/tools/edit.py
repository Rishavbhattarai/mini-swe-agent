"""Line-range replace edit tool, with a pre-commit syntax guardrail for Python
files (mirrors SWE-agent's edit validation/linting before an edit is accepted)."""
from __future__ import annotations

import ast
from dataclasses import dataclass

from mini_swe_agent.tools.base import Executor, ToolResult

CONTEXT_LINES = 3


@dataclass
class EditTool:
    executor: Executor
    name: str = "edit"
    description: str = (
        "Replace lines [start_line, end_line] (1-indexed, inclusive) in a file with new content. "
        "Python edits are syntax-checked before being committed; invalid edits are rejected."
    )

    @property
    def json_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                    "replacement": {"type": "string", "description": "New text for the given line range."},
                },
                "required": ["path", "start_line", "end_line", "replacement"],
            },
        }

    def __call__(self, path: str, start_line: int, end_line: int, replacement: str, **_ignored) -> ToolResult:
        stdout, stderr, code = self.executor.run(f"cat {path}")
        if code != 0:
            return ToolResult(success=False, output="", error=stderr or f"could not read {path}")

        lines = stdout.splitlines()
        if not (1 <= start_line <= end_line <= len(lines) + 1):
            return ToolResult(
                success=False,
                output="",
                error=f"invalid line range [{start_line}, {end_line}] for a {len(lines)}-line file",
            )

        new_lines = lines[: start_line - 1] + replacement.splitlines() + lines[end_line:]
        new_content = "\n".join(new_lines) + "\n"

        if path.endswith(".py"):
            try:
                ast.parse(new_content)
            except SyntaxError as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"edit rejected: resulting file has a syntax error: {e}",
                )

        write_result = self.executor.write_file(path, new_content)
        if not write_result:
            return ToolResult(success=False, output="", error=f"failed to write {path}")

        preview_start = max(1, start_line - CONTEXT_LINES)
        preview_end = min(len(new_lines), start_line - 1 + len(replacement.splitlines()) + CONTEXT_LINES)
        preview = "\n".join(
            f"{i + 1}: {new_lines[i]}" for i in range(preview_start - 1, preview_end)
        )
        return ToolResult(success=True, output=f"Edit applied. Preview:\n{preview}", metadata={"path": path})
