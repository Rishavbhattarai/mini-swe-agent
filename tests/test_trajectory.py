import json
import tempfile
from pathlib import Path

from mini_swe_agent.agent.trajectory import Step, Trajectory


def test_trajectory_logs_steps_as_jsonl():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "traj.jsonl"
        trajectory = Trajectory(instance_id="demo-1")
        trajectory.attach_log(log_path)

        trajectory.add_step(Step(role="assistant", content="thinking"))
        trajectory.add_step(Step(role="tool", content="result", tool_result={"success": True, "output": "ok"}))
        trajectory.finish(stop_reason="submitted", final_patch="diff --git a b", wall_clock_s=1.5)

        assert trajectory.total_steps == 2
        assert trajectory.stop_reason == "submitted"

        lines = log_path.read_text().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["role"] == "assistant"
        assert json.loads(lines[1])["role"] == "tool"


def test_reattaching_log_truncates_previous_run():
    """A second attach_log to the same path (e.g. a batch retry re-running an
    instance from scratch) must not append after a prior attempt's steps --
    confirmed confusing on a live run where a duplicate-process race left two
    full trajectories stacked in one file."""
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "traj.jsonl"

        first = Trajectory(instance_id="demo-1")
        first.attach_log(log_path)
        first.add_step(Step(role="assistant", content="first attempt"))

        second = Trajectory(instance_id="demo-1")
        second.attach_log(log_path)
        second.add_step(Step(role="assistant", content="second attempt"))

        lines = log_path.read_text().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["content"] == "second attempt"
