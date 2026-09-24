"""Wraps the official swebench package: starts the per-instance Docker
container (preferring the official prebuilt image), runs the agent inside it,
writes predictions.jsonl in the exact schema swebench.harness.run_evaluation
expects, and invokes it for FAIL_TO_PASS/PASS_TO_PASS scoring -- this is the
ONLY path that produces official fix-rate numbers (see env/docker_repo.py and
README for the local-clone caveat).

Verified against the installed swebench==3.0.17 API.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from swebench.harness.run_evaluation import main as swebench_run_evaluation

from mini_swe_agent.agent.loop import Agent
from mini_swe_agent.config import RunConfig
from mini_swe_agent.dataset.swebench_lite import Instance
from mini_swe_agent.env.docker_repo import DockerRepoExecutor
from mini_swe_agent.llm.ollama_client import OllamaClient
from mini_swe_agent.tools.registry import build_registry


def run_one_docker(instance: Instance, config: RunConfig, results_dir: str) -> dict:
    executor = DockerRepoExecutor.start_for_instance(instance.raw_row)
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
        # Best-effort cleanup: a Docker hiccup here (daemon paused, network
        # blip) must not discard an already-completed agent result -- confirmed
        # via a live run where Docker Desktop was paused mid-batch and
        # container.stop() raised after the agent had already finished.
        try:
            executor.stop()
        except Exception:
            pass

    return {
        "instance_id": instance.instance_id,
        "model_patch": trajectory.final_patch or "",
        "model_name_or_path": config.llm.model,
        "stop_reason": trajectory.stop_reason,
        "total_steps": trajectory.total_steps,
        "wall_clock_s": trajectory.wall_clock_s,
    }


def write_predictions(predictions: list[dict], results_dir: str) -> str:
    """Writes predictions.jsonl in swebench's exact required schema (extra keys
    would be harmless to swebench itself, but we keep it strict), plus a
    run_metadata.jsonl sidecar carrying our own fields (stop_reason,
    total_steps, wall_clock_s) that scripts/report.py's trajectory stats read
    -- predictions.jsonl alone can't carry them without risking schema drift
    against swebench's own reader."""
    path = Path(results_dir) / "predictions.jsonl"
    metadata_path = Path(results_dir) / "run_metadata.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f, open(metadata_path, "w") as mf:
        for p in predictions:
            f.write(json.dumps({
                "instance_id": p["instance_id"],
                "model_patch": p["model_patch"],
                "model_name_or_path": p["model_name_or_path"],
            }) + "\n")
            mf.write(json.dumps({
                "instance_id": p["instance_id"],
                "stop_reason": p.get("stop_reason"),
                "total_steps": p.get("total_steps"),
                "wall_clock_s": p.get("wall_clock_s"),
            }) + "\n")
    return str(path)


def run_swebench_evaluation(
    predictions_path: str,
    run_id: str,
    results_dir: str,
    dataset_name: str = "princeton-nlp/SWE-bench_Lite",
    split: str = "test",
    max_workers: int = 4,
    timeout: int = 1800,
) -> str:
    """Invokes swebench.harness.run_evaluation.main() directly (importable,
    stable entrypoint in swebench 3.x). NOTE: swebench 3.0.17's
    make_run_report() ignores the `report_dir` kwarg and always writes
    "<model>.<run_id>.json" to the current working directory -- so we chdir
    into results_dir for the call and normalize the output to
    eval_report.json."""
    report_dir = Path(results_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = str(Path(predictions_path).resolve())

    original_cwd = os.getcwd()
    os.chdir(report_dir)
    try:
        swebench_run_evaluation(
            dataset_name=dataset_name,
            split=split,
            instance_ids=[],
            predictions_path=predictions_path,
            max_workers=max_workers,
            force_rebuild=False,
            cache_level="env",
            clean=False,
            open_file_limit=4096,
            run_id=run_id,
            timeout=timeout,
            # namespace=None makes run_evaluation build images locally when
            # needed (it calls build_env_images itself) instead of only ever
            # pulling from Docker Hub under namespace="swebench". Confirmed
            # necessary: not every SWE-bench Lite instance has a published
            # remote image (astropy__astropy-14365 doesn't), and our own
            # agent execution already falls back to a local build for those
            # -- scoring must be able to do the same or it 404s on an
            # instance we already have a real patch for.
            namespace=None,
            rewrite_reports=False,
            modal=False,
            instance_image_tag="latest",
            report_dir=str(report_dir),
        )
    finally:
        os.chdir(original_cwd)

    produced = sorted(report_dir.glob(f"*.{run_id}.json"))
    final_path = report_dir / "eval_report.json"
    if produced:
        final_path.write_text(produced[-1].read_text())
    return str(final_path)
