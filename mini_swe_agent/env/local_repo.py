"""Fast dev-loop executor: clones a repo at a given commit into a scratch
working directory and runs tool commands directly on the host shell.

NOT used for official scoring — only for debugging the agent loop itself
before/without Docker. See env/docker_repo.py for the faithful eval path."""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LocalRepoExecutor:
    workdir: str

    @classmethod
    def clone_at_commit(cls, repo: str, base_commit: str, scratch_root: str | None = None) -> "LocalRepoExecutor":
        root = Path(scratch_root or tempfile.mkdtemp(prefix="mini-swe-"))
        target = root / repo.replace("/", "__")
        url = f"https://github.com/{repo}.git"
        subprocess.run(["git", "clone", "--quiet", url, str(target)], check=True)
        subprocess.run(["git", "checkout", "--quiet", base_commit], cwd=target, check=True)
        return cls(workdir=str(target))

    def run(self, cmd: str, cwd: str | None = None) -> tuple[str, str, int]:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd or self.workdir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.stdout, result.stderr, result.returncode

    def write_file(self, path: str, content: str) -> bool:
        full_path = Path(self.workdir) / path
        try:
            full_path.write_text(content)
            return True
        except OSError:
            return False
