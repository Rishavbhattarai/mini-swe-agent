"""Ablation "limited window" — the core SWE-agent ACI choice: a scrollable,
line-numbered viewer with per-session cursor state, instead of full-file dumps.
Keeps the model's context budget bounded regardless of file size."""
from __future__ import annotations

from dataclasses import dataclass, field

from mini_swe_agent.tools.base import Executor, ToolResult


@dataclass
class WindowedFileOpenTool:
    executor: Executor
    window: int = 100
    name: str = "open_file"
    description: str = (
        "Open a file and view a window of lines around a given line (default: start of file). "
        "Use 'line' to jump to a location, or omit it to continue from the current cursor."
    )
    _cursor: dict[str, int] = field(default_factory=dict)  # path -> current center line

    @property
    def json_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "line": {"type": "integer", "description": "1-indexed line to center the window on."},
                    "scroll": {
                        "type": "string",
                        "enum": ["down", "up"],
                        "description": "Scroll the window by one page instead of jumping to a specific line.",
                    },
                },
                "required": ["path"],
            },
        }

    def _line_count(self, path: str) -> int:
        stdout, _, code = self.executor.run(f"wc -l < {path}")
        if code != 0:
            return 0
        try:
            return int(stdout.strip())
        except ValueError:
            return 0

    def __call__(self, path: str, line: int | None = None, scroll: str | None = None, **_ignored) -> ToolResult:
        total = self._line_count(path)
        if total == 0:
            stdout, stderr, code = self.executor.run(f"test -f {path}")
            if code != 0:
                return ToolResult(success=False, output="", error=f"file not found: {path}")

        current = self._cursor.get(path, 1)
        if line is not None:
            current = line
        elif scroll == "down":
            current += self.window
        elif scroll == "up":
            current -= self.window

        current = max(1, min(current, max(total, 1)))
        start = max(1, current - self.window // 2)
        end = min(total, start + self.window - 1) if total else start + self.window - 1
        self._cursor[path] = current

        stdout, stderr, code = self.executor.run(f"sed -n '{start},{end}p' {path}")
        if code != 0:
            return ToolResult(success=False, output="", error=stderr or f"could not read {path}")

        numbered = "\n".join(
            f"{start + i}: {line_text}" for i, line_text in enumerate(stdout.splitlines())
        )
        footer = f"\n[showing lines {start}-{end} of {total}]" if total else ""
        return ToolResult(
            success=True,
            output=numbered + footer,
            metadata={"path": path, "start": start, "end": end, "total": total},
        )
