"""Faithful eval executor: builds/reuses the SWE-bench instance's Docker image
(base -> env -> instance layer cache, via the `swebench` package) and runs tool
commands via `docker exec` inside a live container, so the agent's own
run_tests calls match the harness's final scoring exactly.

Verified against the installed `swebench==3.0.17` API (see
mini_swe_agent/dataset/swebench_lite.py's Instance.raw_row, which carries the
full HF row this module needs -- our reduced Instance fields aren't enough on
their own for swebench's TestSpec/image-build calls).
"""
from __future__ import annotations

import io
import tarfile
from dataclasses import dataclass

import docker
from docker.errors import APIError, ImageNotFound, NotFound
from swebench.harness.docker_build import build_instance_images
from swebench.harness.test_spec.test_spec import make_test_spec

WORKDIR = "/testbed"


@dataclass
class DockerRepoExecutor:
    container: "docker.models.containers.Container"
    workdir: str = WORKDIR

    @classmethod
    def start_for_instance(cls, raw_row: dict, prefer_remote: bool = True) -> "DockerRepoExecutor":
        """Starts a container for this instance, preferring swebench's official
        prebuilt image on Docker Hub (namespace="swebench", fast, official
        parity) and falling back to a local base->env->instance build (slow,
        first-time only per repo/version) if no prebuilt image exists."""
        client = docker.from_env()
        image_key = None

        if prefer_remote:
            remote_spec = make_test_spec(raw_row, namespace="swebench")
            try:
                client.images.pull(remote_spec.instance_image_key)
                image_key = remote_spec.instance_image_key
            except (ImageNotFound, NotFound, APIError):
                image_key = None

        if image_key is None:
            local_spec = make_test_spec(raw_row)
            # build_instance_images requires an explicit tag -- its default
            # (None) hits an assertion inside make_test_spec ("instance_image_tag
            # cannot be None"), confirmed via a real crash on a local-build
            # fallback for an instance with no prebuilt remote image.
            #
            # It also does NOT raise on a failed build -- it returns
            # (successful, failed) lists and just prints. Confirmed via a real
            # crash: an ignored build failure left client.containers.run()
            # trying to run a nonexistent local image, which docker then
            # attempted to *pull* from Docker Hub, failing with a confusing
            # unrelated "pull access denied" error instead of a clear build
            # failure. Check the image actually exists locally before running.
            _, failed = build_instance_images(client=client, dataset=[raw_row], max_workers=1, tag="latest")
            if failed:
                raise RuntimeError(
                    f"Failed to build local Docker image for instance "
                    f"{raw_row.get('instance_id')}: {failed}"
                )
            image_key = local_spec.instance_image_key

        try:
            client.images.get(image_key)
        except ImageNotFound as e:
            raise RuntimeError(
                f"Docker image '{image_key}' not found locally after build/pull step "
                f"for instance {raw_row.get('instance_id')}."
            ) from e

        container = client.containers.run(
            image_key,
            command="sleep infinity",
            detach=True,
            working_dir=WORKDIR,
        )
        return cls(container=container, workdir=WORKDIR)

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
