"""Runs the agent against one SWE-bench instance, either locally (dev-loop,
unscored) or in Docker (faithful, scoreable), and returns a prediction dict
plus the full trajectory."""
from __future__ import annotations

from pathlib import Path

from mini_swe_agent.agent.loop import Agent
from mini_swe_agent.config import RunConfig
from mini_swe_agent.dataset.swebench_lite import Instance
from mini_swe_agent.env.local_repo import LocalRepoExecutor
from mini_swe_agent.llm.ollama_client import OllamaClient
from mini_swe_agent.tools.registry import build_registry


def run_one_local(instance: Instance, config: RunConfig, results_dir: str) -> dict:
    """Dev-loop mode: local clone, no Docker. NOT used for official scoring --
    see harness/swebench_eval.py for the Docker-based faithful path."""
    executor = LocalRepoExecutor.clone_at_commit(instance.repo, instance.base_commit)

    llm = OllamaClient(
        model=config.llm.model,
        host=config.llm.host,
        temperature=config.llm.temperature,
        request_timeout_s=config.llm.request_timeout_s,
    )
    # See harness/swebench_eval.py for why this uses PASS_TO_PASS, not
    # FAIL_TO_PASS: the latter don't exist until the gold patch is applied.
    test_cmd = (
        f"python -m pytest {' '.join(instance.pass_to_pass[:10])}"
        if instance.pass_to_pass
        else None
    )
    registry = build_registry(
        executor=executor,
        tools_config=config.tools,
        file_view_window=config.agent.file_view_window,
        default_test_cmd=test_cmd,
    )
    agent = Agent(llm=llm, registry=registry, agent_config=config.agent, llm_config=config.llm)

    log_path = Path(results_dir) / "trajectories" / f"{instance.instance_id}.jsonl"
    trajectory = agent.run(instance.instance_id, instance.problem_statement, log_path=str(log_path))

    return {
        "instance_id": instance.instance_id,
        "model_patch": trajectory.final_patch or "",
        "model_name_or_path": config.llm.model,
        "stop_reason": trajectory.stop_reason,
        "total_steps": trajectory.total_steps,
        "wall_clock_s": trajectory.wall_clock_s,
    }
