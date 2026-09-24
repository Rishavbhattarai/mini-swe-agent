"""Aggregates one or more results/<run>/eval_report.json files into a fix-rate
summary/comparison table (Markdown), written per-run as summary.md and, when
multiple runs are given, as a comparison.md with a delta-vs-baseline column."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_report(run_dir: str) -> dict:
    path = Path(run_dir) / "eval_report.json"
    if not path.exists():
        return {"resolved_instances": 0, "submitted_instances": 0}
    return json.loads(path.read_text())


def _fix_rate(report: dict) -> float:
    # Fix rate is over instances we actually submitted, not swebench's
    # `total_instances` (which is the whole dataset split, e.g. 300 for Lite,
    # even when we only ran a small subset).
    submitted = report.get("submitted_instances", 0)
    resolved = report.get("resolved_instances", 0)
    return (resolved / submitted) if submitted else 0.0


def _trajectory_stats(run_dir: str) -> dict:
    metadata_path = Path(run_dir) / "run_metadata.jsonl"
    if not metadata_path.exists():
        return {"avg_steps": 0.0, "avg_wall_clock_s": 0.0, "pct_max_steps": 0.0}
    rows = [json.loads(line) for line in metadata_path.read_text().splitlines() if line.strip()]
    if not rows:
        return {"avg_steps": 0.0, "avg_wall_clock_s": 0.0, "pct_max_steps": 0.0}
    avg_steps = sum(r.get("total_steps", 0) for r in rows) / len(rows)
    avg_wall_clock = sum(r.get("wall_clock_s", 0.0) for r in rows) / len(rows)
    pct_max_steps = sum(1 for r in rows if r.get("stop_reason") == "max_steps") / len(rows) * 100
    return {"avg_steps": avg_steps, "avg_wall_clock_s": avg_wall_clock, "pct_max_steps": pct_max_steps}


def build_report(run_dirs: list[str]) -> None:
    rows = []
    for run_dir in run_dirs:
        report = _load_report(run_dir)
        stats = _trajectory_stats(run_dir)
        rows.append(
            {
                "run": Path(run_dir).name,
                "fix_rate": _fix_rate(report),
                "resolved": report.get("resolved_instances", 0),
                "total": report.get("submitted_instances", 0),
                **stats,
            }
        )
        Path(run_dir, "summary.md").write_text(_format_single(rows[-1]))

    table = _format_comparison(rows)
    print(table)
    if len(run_dirs) > 1:
        Path("results", "comparison.md").parent.mkdir(parents=True, exist_ok=True)
        Path("results", "comparison.md").write_text(table)


def _format_single(row: dict) -> str:
    return (
        f"# {row['run']}\n\n"
        f"- Fix rate: {row['fix_rate']:.1%} ({row['resolved']}/{row['total']})\n"
        f"- Avg steps: {row['avg_steps']:.1f}\n"
        f"- Avg wall clock: {row['avg_wall_clock_s']:.1f}s\n"
        f"- % hit max_steps: {row['pct_max_steps']:.1f}%\n"
    )


def _format_comparison(rows: list[dict]) -> str:
    baseline = rows[0]["fix_rate"] if rows else 0.0
    lines = ["| Run | Fix Rate | Resolved | Delta vs baseline | Avg Steps | Avg Wall Clock (s) |",
             "|---|---|---|---|---|---|"]
    for row in rows:
        delta = row["fix_rate"] - baseline
        lines.append(
            f"| {row['run']} | {row['fix_rate']:.1%} | {row['resolved']}/{row['total']} "
            f"| {delta:+.1%} | {row['avg_steps']:.1f} | {row['avg_wall_clock_s']:.1f} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    build_report(sys.argv[1:])
