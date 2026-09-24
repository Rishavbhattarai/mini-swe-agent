"""Stop conditions for the agent loop, checked each iteration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from mini_swe_agent.llm.base import ToolCall


@dataclass
class StopCheck:
    stopped: bool
    reason: Optional[str] = None


def _is_cycling(call_history: list[ToolCall], max_period: int, min_repeats: int) -> bool:
    """Detects A,B,A,B,... (or longer) cycles, not just immediate exact duplicates.
    For each candidate period p, checks whether the last `min_repeats` repetitions
    of a length-p block are all identical."""
    signatures = [(c.name, tuple(sorted(c.arguments.items()))) for c in call_history]
    for period in range(1, max_period + 1):
        window = period * min_repeats
        if len(signatures) < window:
            continue
        tail = signatures[-window:]
        block = tail[:period]
        if all(tail[i * period:(i + 1) * period] == block for i in range(min_repeats)):
            return True
    return False


def check_stop(
    tool_call: Optional[ToolCall],
    tool_result_success: Optional[bool],
    step_count: int,
    max_steps: int,
    call_history: list[ToolCall],
    stop_on_repeated_call: bool,
    auto_stop_on_tests_pass: bool,
) -> StopCheck:
    if tool_call is not None and tool_call.name == "submit_patch" and tool_result_success:
        return StopCheck(stopped=True, reason="submitted")

    if step_count >= max_steps:
        return StopCheck(stopped=True, reason="max_steps")

    if stop_on_repeated_call and _is_cycling(call_history, max_period=3, min_repeats=3):
        return StopCheck(stopped=True, reason="repeated_call")

    if (
        auto_stop_on_tests_pass
        and tool_call is not None
        and tool_call.name == "run_tests"
        and tool_result_success
    ):
        return StopCheck(stopped=True, reason="tests_pass_auto_stop")

    return StopCheck(stopped=False)
