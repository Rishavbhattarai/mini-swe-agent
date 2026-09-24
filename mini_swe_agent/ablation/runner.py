"""Runs batch_runner across a list of ablation configs, tags each results dir
by config name, scores each with the swebench harness, then hands off to
scripts/report.py for a single cross-config comparison table."""
from __future__ import annotations

from pathlib import Path

from mini_swe_agent.config import RunConfig
from mini_swe_agent.dataset.swebench_lite import Instance, load_instances
from mini_swe_agent.harness.batch_runner import run_batch
from mini_swe_agent.harness.swebench_eval import run_swebench_evaluation


def run_ablation(
    config_paths: list[str],
    limit: int | None,
    subset_file: str | None = None,
    base_results_dir: str = "results",
) -> list[str]:
    """Returns the list of results directories produced, one per config, ready
    for scripts/report.py to compare."""
    run_dirs = []
    for config_path in config_paths:
        config_name = Path(config_path).stem
        config = RunConfig.load(config_path)
        if limit is not None:
            config.dataset.limit = limit
        if subset_file is not None:
            config.dataset.subset_file = subset_file

        instances: list[Instance] = load_instances(
            name=config.dataset.name,
            split=config.dataset.split,
            limit=config.dataset.limit,
            subset_file=config.dataset.subset_file,
        )

        run_dir = str(Path(base_results_dir) / config_name)
        run_batch(instances, config, run_dir)

        if config.eval.docker:
            run_swebench_evaluation(
                predictions_path=str(Path(run_dir) / "predictions.jsonl"),
                run_id=config_name,
                results_dir=run_dir,
                dataset_name=config.dataset.name,
                split=config.dataset.split,
                timeout=config.eval.test_timeout_s,
            )

        run_dirs.append(run_dir)

    return run_dirs
