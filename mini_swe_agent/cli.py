"""CLI entrypoints: run-one, run-batch, evaluate, ablate, report."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mini_swe_agent.ablation.runner import run_ablation
from mini_swe_agent.config import RunConfig
from mini_swe_agent.dataset.swebench_lite import load_instances
from mini_swe_agent.harness.batch_runner import run_batch
from mini_swe_agent.harness.single_instance import run_one_local
from mini_swe_agent.harness.swebench_eval import run_one_docker, run_swebench_evaluation, write_predictions


def cmd_run_one(args: argparse.Namespace) -> None:
    config = RunConfig.load(args.config)
    if args.docker is not None:
        config.eval.docker = args.docker

    instances = load_instances(
        name=config.dataset.name, split=config.dataset.split, instance_ids=[args.instance_id]
    )
    if not instances:
        print(f"instance_id '{args.instance_id}' not found in {config.dataset.name}", file=sys.stderr)
        sys.exit(1)

    results_dir = args.results_dir or f"{config.results_dir}/single_{args.instance_id}"
    Path(results_dir).mkdir(parents=True, exist_ok=True)
    config.dump_snapshot(Path(results_dir) / "config_used.yaml")

    run_fn = run_one_docker if config.eval.docker else run_one_local
    result = run_fn(instances[0], config, results_dir)
    write_predictions([result], results_dir)
    print(result)


def cmd_run_batch(args: argparse.Namespace) -> None:
    config = RunConfig.load(args.config)
    if args.limit is not None:
        config.dataset.limit = args.limit
    if args.subset is not None:
        config.dataset.subset_file = args.subset

    instances = load_instances(
        name=config.dataset.name,
        split=config.dataset.split,
        limit=config.dataset.limit,
        subset_file=config.dataset.subset_file,
    )
    results_dir = args.results_dir or f"{config.results_dir}/{Path(args.config).stem if args.config else 'default'}"
    predictions = run_batch(instances, config, results_dir)
    print(f"Ran {len(predictions)} instances. Results in {results_dir}")


def cmd_evaluate(args: argparse.Namespace) -> None:
    snapshot_path = Path(args.run_dir) / "config_used.yaml"
    config = RunConfig.load(str(snapshot_path)) if snapshot_path.exists() else RunConfig()
    run_swebench_evaluation(
        predictions_path=str(Path(args.run_dir) / "predictions.jsonl"),
        run_id=Path(args.run_dir).name,
        results_dir=args.run_dir,
        dataset_name=config.dataset.name,
        split=config.dataset.split,
        timeout=config.eval.test_timeout_s,
    )


def cmd_ablate(args: argparse.Namespace) -> None:
    run_dirs = run_ablation(args.configs, limit=args.limit, base_results_dir=args.results_dir)
    print("Ablation run dirs:")
    for d in run_dirs:
        print(f"  {d}")
    print("Run `python scripts/report.py " + " ".join(run_dirs) + "` to compare fix rates.")


def cmd_report(args: argparse.Namespace) -> None:
    # scripts/ lives at the repo root, not inside the installed package, so it
    # must be added to sys.path explicitly before importing.
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root))
    from scripts.report import build_report

    build_report(args.run_dirs)


def main() -> None:
    parser = argparse.ArgumentParser(prog="mini-swe")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run_one = sub.add_parser("run-one", help="Run the agent on a single instance.")
    p_run_one.add_argument("--instance-id", required=True)
    p_run_one.add_argument("--config", default="configs/default.yaml")
    p_run_one.add_argument("--results-dir", default=None)
    p_run_one.add_argument("--docker", type=lambda s: s.lower() == "true", default=None)
    p_run_one.set_defaults(func=cmd_run_one)

    p_run_batch = sub.add_parser("run-batch", help="Run the agent on a batch of instances.")
    p_run_batch.add_argument("--config", default="configs/default.yaml")
    p_run_batch.add_argument("--limit", type=int, default=None)
    p_run_batch.add_argument("--subset", default=None, help="Path to an instance_id allowlist file.")
    p_run_batch.add_argument("--results-dir", default=None)
    p_run_batch.set_defaults(func=cmd_run_batch)

    p_evaluate = sub.add_parser("evaluate", help="Score a run's predictions.jsonl via the official swebench harness.")
    p_evaluate.add_argument("--run-dir", required=True)
    p_evaluate.set_defaults(func=cmd_evaluate)

    p_ablate = sub.add_parser("ablate", help="Run and score multiple configs for an ACI ablation comparison.")
    p_ablate.add_argument("--configs", nargs="+", required=True)
    p_ablate.add_argument("--limit", type=int, default=None)
    p_ablate.add_argument("--results-dir", default="results")
    p_ablate.set_defaults(func=cmd_ablate)

    p_report = sub.add_parser("report", help="Build a fix-rate comparison table across run dirs.")
    p_report.add_argument("run_dirs", nargs="+")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
