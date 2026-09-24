"""Renders a styled terminal-session SVG for the README, from real output
captured off this project (CLI help, real search/open_file tool calls from
the astropy__astropy-12907 trajectory, and the real pytest run) -- not
fabricated sample output."""
from __future__ import annotations

from rich.console import Console
from rich.text import Text

console = Console(record=True, width=100)


def prompt(cmd: str) -> None:
    console.print(Text("$ ", style="bold green") + Text(cmd, style="bold white"))


def dim(line: str) -> None:
    console.print(Text(line, style="grey70"))


def tool_call(name: str, args: str) -> None:
    console.print(Text(f"  -> {name}", style="bold cyan") + Text(f" {args}", style="grey58"))


def tool_output(line: str) -> None:
    console.print(Text(f"     {line}", style="grey50"))


prompt("mini-swe run-one --instance-id astropy__astropy-12907 --config configs/default.yaml --docker true")
dim("Starting container from swebench/sweb.eval.arm64.astropy_1776_astropy-12907:latest ...")
console.print()
tool_call("search", "{'query': 'is_separable', 'path': '.', 'file_pattern': '*.py'}")
tool_output("astropy/modeling/separable.py (13 matches):")
tool_output("  24: __all__ = [\"is_separable\", \"separability_matrix\"]")
tool_output("  27: def is_separable(transform):")
tool_call("open_file", "{'path': 'astropy/modeling/separable.py'}")
tool_output("1: # Licensed under a 3-clause BSD style license - see LICENSE.rst")
tool_output("...")
console.print()
console.print(Text("{'instance_id': 'astropy__astropy-12907', 'stop_reason': 'max_steps', 'total_steps': 80,", style="grey50"))
console.print(Text(" 'wall_clock_s': 455.0, 'model_name_or_path': 'qwen2.5-coder:7b'}", style="grey50"))
console.print()

prompt("mini-swe evaluate --run-dir results/mvp_docker")
dim("Total instances: 300")
dim("Instances submitted: 1")
dim("Instances completed: 0")
dim("Instances resolved: 0")
dim("Instances with empty patches: 1")
console.print(Text("Report written to eval_report.json", style="bold yellow"))
console.print()

prompt("pytest -q")
console.print(Text("." * 18 + "                                                       [100%]", style="bold green"))
console.print(Text("18 passed in 1.41s", style="bold green"))

console.save_svg(
    "docs/assets/demo.svg",
    title="mini-swe-agent",
    font_aspect_ratio=0.58,
)
print("wrote docs/assets/demo.svg")
