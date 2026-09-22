from __future__ import annotations

import json
import shutil
import socket
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from finance_agent.harness.analysis_schema import MockDryRunResult
from finance_agent.sandbox.provider import SandboxExecutionRequest


@dataclass(frozen=True)
class FirecrackerConfig:
    firecracker_bin: Path
    kernel_image_path: Path
    rootfs_path: Path
    work_dir: Path
    jailer_bin: Path | None = None
    use_jailer: bool = True
    boot_args: str = "console=ttyS0 reboot=k panic=1 pci=off"


class FirecrackerSandboxProvider:
    """Target production sandbox provider skeleton.

    Firecracker requires Linux/KVM, so this provider is intentionally not used
    by default on the Mac development machine. It captures the API sequence and
    host contract we will run on a Linux sandbox host.
    """

    name = "firecracker"

    def __init__(self, config: FirecrackerConfig):
        self.config = config

    def execute(self, request: SandboxExecutionRequest) -> MockDryRunResult:
        started = time.time()
        try:
            self._validate_host()
            with tempfile.TemporaryDirectory(dir=self.config.work_dir) as raw_tmp:
                vm_dir = Path(raw_tmp)
                socket_path = vm_dir / "firecracker.sock"
                input_path = vm_dir / "input.json"
                output_path = vm_dir / "output.json"
                events_path = vm_dir / "events.jsonl"
                rootfs_path = self._prepare_rootfs(vm_dir)
                input_path.write_text(
                    json.dumps(
                        {
                            "method": request.method.model_dump(mode="json"),
                            "rows": request.rows,
                            "dataset_name": request.dataset_name,
                            "output_path": "/sandbox/output.json",
                            "events_path": "/sandbox/events.jsonl",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                process = self._start_firecracker(socket_path)
                try:
                    self._put_json(socket_path, "/machine-config", {"vcpu_count": request.vcpu_count, "mem_size_mib": request.memory_mib})
                    self._put_json(
                        socket_path,
                        "/boot-source",
                        {"kernel_image_path": str(self.config.kernel_image_path), "boot_args": self.config.boot_args},
                    )
                    self._put_json(
                        socket_path,
                        "/drives/rootfs",
                        {
                            "drive_id": "rootfs",
                            "path_on_host": str(rootfs_path),
                            "is_root_device": True,
                            "is_read_only": False,
                        },
                    )
                    # No /network-interfaces call: the guest has no network device.
                    self._put_json(socket_path, "/actions", {"action_type": "InstanceStart"})
                    self._wait_for_output(output_path, timeout_seconds=request.timeout_seconds)
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()

                elapsed_ms = int((time.time() - started) * 1000)
                output = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else {}
                return MockDryRunResult(
                    status="passed",
                    output=output.get("result", output),
                    input_summary={
                        "fixture": request.dataset_name,
                        "row_count": len(request.rows),
                        "elapsed_ms": elapsed_ms,
                        "runner": request.method.method_type,
                        "sandbox_provider": self.name,
                        "network_disabled": True,
                        "events_path": str(events_path),
                        "real_database_used": False,
                    },
                )
        except Exception as exc:  # noqa: BLE001 - provider returns a structured sandbox failure
            return MockDryRunResult(
                status="failed",
                errors=[f"{type(exc).__name__}: {exc}"],
                input_summary={
                    "fixture": request.dataset_name,
                    "row_count": len(request.rows),
                    "runner": request.method.method_type,
                    "sandbox_provider": self.name,
                    "network_disabled": True,
                    "real_database_used": False,
                },
            )

    def _validate_host(self) -> None:
        if not Path("/dev/kvm").exists():
            raise RuntimeError("Firecracker requires Linux/KVM; /dev/kvm was not found")
        for path in [self.config.firecracker_bin, self.config.kernel_image_path, self.config.rootfs_path]:
            if not path.exists():
                raise RuntimeError(f"Firecracker asset not found: {path}")
        self.config.work_dir.mkdir(parents=True, exist_ok=True)

    def _prepare_rootfs(self, vm_dir: Path) -> Path:
        rootfs_copy = vm_dir / "rootfs.ext4"
        shutil.copyfile(self.config.rootfs_path, rootfs_copy)
        return rootfs_copy

    def _start_firecracker(self, socket_path: Path) -> subprocess.Popen:
        command = [str(self.config.firecracker_bin), "--api-sock", str(socket_path)]
        return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def _put_json(self, socket_path: Path, path: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        request = (
            f"PUT {path} HTTP/1.1\r\n"
            "Host: localhost\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "\r\n"
        ).encode() + body
        response = self._send_http_over_unix_socket(socket_path, request)
        if b" 2" not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(response.decode("utf-8", errors="replace"))

    def _send_http_over_unix_socket(self, socket_path: Path, request: bytes) -> bytes:
        deadline = time.time() + 5
        while not socket_path.exists():
            if time.time() > deadline:
                raise RuntimeError(f"Firecracker API socket not created: {socket_path}")
            time.sleep(0.05)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(socket_path))
            client.sendall(request)
            return client.recv(65536)

    def _wait_for_output(self, output_path: Path, timeout_seconds: int) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if output_path.exists():
                return
            time.sleep(0.1)
        raise TimeoutError(f"Firecracker sandbox timed out after {timeout_seconds}s")
