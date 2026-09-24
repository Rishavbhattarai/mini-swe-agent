"""Ablation "better search": ripgrep, results grouped by file with match counts,
so the model sees which files are most relevant before opening any of them
(mirrors SWE-agent's search_dir/search_file grouping).

Falls back to `grep -rn` when `rg` isn't installed in the execution
environment (confirmed missing in SWE-bench's official conda-based instance
images) -- grep's `file:lineno:text` output is parsed identically, so the
grouping/ranking logic is shared either way."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from mini_swe_agent.tools.base import Executor, ToolResult

MAX_FILES = 20
MAX_LINES_PER_FILE = 5


@dataclass
class RipgrepSearchTool:
    executor: Executor
    name: str = "search"
    description: str = (
        "Search for a literal string or regex across files (ripgrep, results grouped "
        "by file and ranked by match density)."
    )
    _rg_available: bool | None = field(default=None, init=False, repr=False)

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

    def _rg_is_available(self) -> bool:
        if self._rg_available is None:
            _, _, code = self.executor.run("command -v rg")
            self._rg_available = code == 0
        return self._rg_available

    def __call__(self, query: str, path: str = ".", file_pattern: str | None = None) -> ToolResult:
        if self._rg_is_available():
            glob = f"--glob '{file_pattern}'" if file_pattern else ""
            cmd = f"rg --line-number --hidden {glob} -- '{query}' {path}"
        else:
            include = f"--include='{file_pattern}'" if file_pattern else ""
            cmd = f"grep -rn {include} -- '{query}' {path}"

        stdout, stderr, code = self.executor.run(cmd)
        if code not in (0, 1):
            return ToolResult(success=False, output="", error=stderr or f"search exited with {code}")
        if not stdout.strip():
            return ToolResult(success=True, output="No matches found.", metadata={"match_count": 0})

        by_file: dict[str, list[str]] = defaultdict(list)
        for line in stdout.splitlines():
            m = re.match(r"^(?P<file>[^:]+):(?P<lineno>\d+):(?P<text>.*)$", line)
            if m:
                by_file[m["file"]].append(f"  {m['lineno']}: {m['text'].strip()}")

        ranked = sorted(by_file.items(), key=lambda kv: len(kv[1]), reverse=True)
        truncated_files = len(ranked) > MAX_FILES
        blocks = []
        for fname, matches in ranked[:MAX_FILES]:
            shown = matches[:MAX_LINES_PER_FILE]
            block = f"{fname} ({len(matches)} match{'es' if len(matches) != 1 else ''}):\n" + "\n".join(shown)
            if len(matches) > MAX_LINES_PER_FILE:
                block += f"\n  ... {len(matches) - MAX_LINES_PER_FILE} more matches in this file"
            blocks.append(block)

        output = "\n\n".join(blocks)
        if truncated_files:
            output += f"\n\n... truncated to top {MAX_FILES} files by match count"
        return ToolResult(
            success=True,
            output=output,
            metadata={"file_count": len(ranked), "truncated": truncated_files},
        )
