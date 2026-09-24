"""Wraps the official swebench package: builds/starts the per-instance Docker
image, runs the agent inside it, writes predictions.jsonl in the exact schema
swebench.harness.run_evaluation expects, and invokes it for FAIL_TO_PASS /
PASS_TO_PASS scoring -- this is the ONLY path that produces official fix-rate
numbers (see env/docker_repo.py and README for the local-clone caveat).

NOTE: the exact swebench image-build helper and run_evaluation entrypoint
differ across package versions. Once `swebench` is installed, confirm:
  - the image-build function to call for a given instance_id (swebench.harness.docker_build)
  - whether to invoke run_evaluation via `python -m swebench.harness.run_evaluation`
    (subprocess, for version-isolation) or a stable importable function
before wiring this module up for real.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from mini_swe_agent.agent.loop import Agent
from mini_swe_agent.config import RunConfig
from mini_swe_agent.dataset.swebench_lite import Instance
from mini_swe_agent.env.docker_repo import DockerRepoExecutor
from mini_swe_agent.llm.ollama_client import OllamaClient
from mini_swe_agent.tools.registry import build_registry


def instance_image_name(instance: Instance) -> str:
    """Naming convention swebench uses for its pre-built per-instance images.
    Verify against the installed swebench version before relying on this."""
    return f"sweb.eval.x86_64.{instance.instance_id}:latest"


def run_one_docker(instance: Instance, config: RunConfig, results_dir: str) -> dict:
    executor = DockerRepoExecutor.start_for_instance(instance_image_name(instance))
    try:
        llm = OllamaClient(
            model=config.llm.model,
            host=config.llm.host,
            temperature=config.llm.temperature,
            request_timeout_s=config.llm.request_timeout_s,
        )
        test_cmd = f"python -m pytest {' '.join(instance.fail_to_pass)}" if instance.fail_to_pass else None
        registry = build_registry(
            executor=executor,
            tools_config=config.tools,
            file_view_window=config.agent.file_view_window,
            default_test_cmd=test_cmd,
        )
        agent = Agent(llm=llm, registry=registry, agent_config=config.agent, llm_config=config.llm)
        log_path = Path(results_dir) / "trajectories" / f"{instance.instance_id}.jsonl"
        trajectory = agent.run(instance.instance_id, instance.problem_statement, log_path=str(log_path))
    finally:
        executor.stop()

    return {
        "instance_id": instance.instance_id,
        "model_patch": trajectory.final_patch or "",
        "model_name_or_path": config.llm.model,
        "stop_reason": trajectory.stop_reason,
        "total_steps": trajectory.total_steps,
        "wall_clock_s": trajectory.wall_clock_s,
    }


def write_predictions(predictions: list[dict], results_dir: str) -> str:
    path = Path(results_dir) / "predictions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for p in predictions:
            f.write(json.dumps({
                "instance_id": p["instance_id"],
                "model_patch": p["model_patch"],
                "model_name_or_path": p["model_name_or_path"],
            }) + "\n")
    return str(path)


def run_swebench_evaluation(predictions_path: str, run_id: str, results_dir: str) -> str:
    """Invokes the official swebench harness via subprocess for version isolation.
    Output report location depends on the installed swebench version's CLI --
    confirm and adjust the `--run-id`/output flags during build-order step 6."""
    report_path = Path(results_dir) / "eval_report.json"
    subprocess.run(
        [
            "python", "-m", "swebench.harness.run_evaluation",
            "--predictions_path", predictions_path,
            "--run_id", run_id,
        ],
        check=True,
    )
    return str(report_path)
