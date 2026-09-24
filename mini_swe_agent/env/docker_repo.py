"""Faithful eval executor: builds/reuses the SWE-bench instance's Docker image
(base -> env -> instance layer cache, via the `swebench` package) and runs tool
commands via `docker exec` inside a live container, so the agent's own
run_tests calls match the harness's final scoring exactly.

NOTE: swebench's public API surface differs across versions -- the exact
build-image helper imported below must be verified against the installed
`swebench` version before first real use (see README build-order step 6).
"""
from __future__ import annotations

import tarfile
import io
from dataclasses import dataclass

import docker


@dataclass
class DockerRepoExecutor:
    container: "docker.models.containers.Container"
    workdir: str = "/testbed"

    @classmethod
    def start_for_instance(cls, instance_image_name: str, workdir: str = "/testbed") -> "DockerRepoExecutor":
        """Starts (or reuses) a container from a pre-built SWE-bench instance image.

        `instance_image_name` should be the image tag produced by swebench's own
        image-build pipeline for a given instance_id (see harness/swebench_eval.py
        and swebench.harness.docker_build for the exact build call once the
        installed package version's API has been confirmed).
        """
        client = docker.from_env()
        container = client.containers.run(
            instance_image_name,
            command="sleep infinity",
            detach=True,
            working_dir=workdir,
        )
        return cls(container=container, workdir=workdir)

    def run(self, cmd: str, cwd: str | None = None) -> tuple[str, str, int]:
        exec_result = self.container.exec_run(
            ["bash", "-lc", cmd],
            workdir=cwd or self.workdir,
            demux=True,
        )
        stdout_b, stderr_b = exec_result.output
        stdout = (stdout_b or b"").decode(errors="replace")
        stderr = (stderr_b or b"").decode(errors="replace")
        return stdout, stderr, exec_result.exit_code

    def write_file(self, path: str, content: str) -> bool:
        """Writes a file into the container via a tar stream (docker exec has no
        direct file-write primitive)."""
        data = content.encode()
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            info = tarfile.TarInfo(name=path.lstrip("/"))
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        tar_buffer.seek(0)
        try:
            self.container.put_archive(self.workdir, tar_buffer)
            return True
        except Exception:
            return False

    def stop(self) -> None:
        self.container.stop()
        self.container.remove()
