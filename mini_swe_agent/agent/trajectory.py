"""Step-by-step agent transcript, JSONL-logged as it happens so a crashed or
killed run is still inspectable and batch runs are resumable."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Step:
    role: str  # "assistant" | "tool" | "system" | "user"
    content: str
    tool_call: Optional[dict[str, Any]] = None  # {"name": str, "arguments": dict}
    tool_result: Optional[dict[str, Any]] = None  # ToolResult as dict
    timestamp: float = field(default_factory=time.time)


@dataclass
class Trajectory:
    instance_id: str
    steps: list[Step] = field(default_factory=list)
    final_patch: Optional[str] = None
    stop_reason: Optional[str] = None
    total_steps: int = 0
    wall_clock_s: float = 0.0
    _log_path: Optional[Path] = None

    def attach_log(self, path: str | Path) -> None:
        self._log_path = Path(path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def add_step(self, step: Step) -> None:
        self.steps.append(step)
        self.total_steps = len(self.steps)
        if self._log_path is not None:
            with open(self._log_path, "a") as f:
                f.write(json.dumps(asdict(step)) + "\n")

    def finish(self, stop_reason: str, final_patch: Optional[str], wall_clock_s: float) -> None:
        self.stop_reason = stop_reason
        self.final_patch = final_patch
        self.wall_clock_s = wall_clock_s
