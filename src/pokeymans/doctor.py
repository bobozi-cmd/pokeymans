"""Host environment diagnostics for Docker, CPU perf, and NVIDIA GPU profiling (nsys/ncu)."""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

from pokeymans.models.runtime import DoctorCheckResult
from pokeymans.runtime.docker import DockerBackend


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _check_docker(docker: DockerBackend) -> DoctorCheckResult:
    if docker.check_available():
        info = docker.info_json() or {}
        ver = info.get("ServerVersion", "available")
        return DoctorCheckResult(
            name="docker-daemon",
            status="ok",
            detail=f"Docker daemon reachable (server {ver})",
        )
    return DoctorCheckResult(
        name="docker-daemon",
        status="fail",
        detail="Docker daemon is not reachable.",
        remediation="Ensure dockerd is running and your user belongs to the `docker` group.",
    )


def _check_perf_event_paranoid(proc_root: Path) -> DoctorCheckResult:
    val_str = _read_text(proc_root / "sys/kernel/perf_event_paranoid")
    if val_str is None:
        return DoctorCheckResult(
            name="kernel.perf_event_paranoid",
            status="skip",
            detail="Not available on this host OS/kernel.",
        )
    try:
        val = int(val_str)
    except ValueError:
        return DoctorCheckResult(
            name="kernel.perf_event_paranoid",
            status="warn",
            detail=f"Unexpected value: {val_str!r}",
        )

    if val <= 1:
        return DoctorCheckResult(
            name="kernel.perf_event_paranoid",
            status="ok",
            detail=f"value={val} (allows CPU perf & nsys CPU backtrace sampling)",
        )
    if val == 2:
        return DoctorCheckResult(
            name="kernel.perf_event_paranoid",
            status="warn",
            detail="value=2 (blocks kernel/CPU backtrace profiling for non-CAP_SYS_ADMIN users)",
            remediation="sudo sysctl -w kernel.perf_event_paranoid=1  # or -1 for full kernel stacks",
        )
    return DoctorCheckResult(
        name="kernel.perf_event_paranoid",
        status="fail",
        detail=f"value={val} (perf_event_open heavily restricted)",
        remediation="sudo sysctl -w kernel.perf_event_paranoid=1",
    )


def _check_kptr_restrict(proc_root: Path) -> DoctorCheckResult:
    val_str = _read_text(proc_root / "sys/kernel/kptr_restrict")
    if val_str is None:
        return DoctorCheckResult(
            name="kernel.kptr_restrict",
            status="skip",
            detail="Not available on this host OS/kernel.",
        )
    if val_str == "0":
        return DoctorCheckResult(
            name="kernel.kptr_restrict",
            status="ok",
            detail="value=0 (kernel symbols readable for flamegraphs)",
        )
    return DoctorCheckResult(
        name="kernel.kptr_restrict",
        status="warn",
        detail=f"value={val_str} (kernel symbols masked in perf flamegraphs)",
        remediation="sudo sysctl -w kernel.kptr_restrict=0",
    )


def _check_host_perf_binary() -> DoctorCheckResult:
    perf_path = shutil.which("perf")
    if perf_path:
        return DoctorCheckResult(
            name="host-perf-binary",
            status="ok",
            detail=f"Found at {perf_path}",
        )
    return DoctorCheckResult(
        name="host-perf-binary",
        status="warn",
        detail="Host `perf` not found (py-spy inside base images still works without host perf).",
        remediation="Optional: sudo apt-get install linux-tools-common linux-tools-$(uname -r)",
    )


def _check_nvidia_gpu(require_gpu: bool) -> tuple[DoctorCheckResult, bool]:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return (
            DoctorCheckResult(
                name="nvidia-gpu",
                status="fail" if require_gpu else "skip",
                detail="nvidia-smi not found on host.",
                remediation="Install NVIDIA driver on the host for GPU pods." if require_gpu else "",
            ),
            False,
        )
    try:
        proc = subprocess.run(
            [smi, "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        summary = f"{len(lines)} GPU(s): {lines[0]}" if lines else "nvidia-smi ok"
        return (DoctorCheckResult(name="nvidia-gpu", status="ok", detail=summary), True)
    except (OSError, subprocess.SubprocessError) as exc:
        return (
            DoctorCheckResult(
                name="nvidia-gpu",
                status="fail" if require_gpu else "warn",
                detail=f"nvidia-smi failed: {exc}",
                remediation="Check NVIDIA driver status (`nvidia-smi`).",
            ),
            False,
        )


def _check_nvidia_toolkit(docker: DockerBackend, has_gpu: bool, require_gpu: bool) -> DoctorCheckResult:
    if not has_gpu and not require_gpu:
        return DoctorCheckResult(
            name="nvidia-container-toolkit",
            status="skip",
            detail="No host NVIDIA GPU detected.",
        )
    info = docker.info_json() or {}
    runtimes = info.get("Runtimes") or {}
    has_ctk = shutil.which("nvidia-ctk") is not None
    if "nvidia" in runtimes or has_ctk:
        return DoctorCheckResult(
            name="nvidia-container-toolkit",
            status="ok",
            detail="NVIDIA container runtime / nvidia-ctk detected.",
        )
    return DoctorCheckResult(
        name="nvidia-container-toolkit",
        status="fail" if require_gpu else "warn",
        detail="NVIDIA container runtime not detected in Docker.",
        remediation="Install nvidia-container-toolkit and run `sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker`.",
    )


def _check_nvidia_ncu_counters(proc_root: Path, has_gpu: bool, require_gpu: bool) -> DoctorCheckResult:
    params_path = proc_root / "driver/nvidia/params"
    text = _read_text(params_path)
    if text is None:
        if not has_gpu and not require_gpu:
            return DoctorCheckResult(
                name="nvidia-ncu-counters",
                status="skip",
                detail="NVIDIA kernel driver params not present.",
            )
        return DoctorCheckResult(
            name="nvidia-ncu-counters",
            status="warn",
            detail=f"Cannot read {params_path}; unable to verify RmProfilingAdminOnly.",
        )

    admin_only: str | None = None
    for line in text.splitlines():
        if line.startswith("RmProfilingAdminOnly:"):
            admin_only = line.split(":", 1)[1].strip()
            break

    if admin_only == "0":
        return DoctorCheckResult(
            name="nvidia-ncu-counters",
            status="ok",
            detail="RmProfilingAdminOnly=0 (ncu hardware performance counters enabled)",
        )
    return DoctorCheckResult(
        name="nvidia-ncu-counters",
        status="warn",
        detail=f"RmProfilingAdminOnly={admin_only or '1'} (`ncu` may fail with ERR_NVGPUCTRPERM in non-privileged pods)",
        remediation=(
            'echo "options nvidia NVreg_RestrictProfilingToAdminUsers=0" | '
            "sudo tee /etc/modprobe.d/nvidia-perf.conf && sudo update-initramfs -u && sudo reboot"
        ),
    )


def run_doctor(
    *,
    docker: DockerBackend | None = None,
    check_gpu: bool = False,
    proc_root: Path = Path("/proc"),
) -> list[DoctorCheckResult]:
    """Run host readiness checks for Docker, CPU profiling, and NVIDIA nsys/ncu."""
    backend = docker or DockerBackend()
    results: list[DoctorCheckResult] = [_check_docker(backend)]

    if platform.system() == "Linux" or (proc_root / "sys/kernel").exists():
        results.append(_check_perf_event_paranoid(proc_root))
        results.append(_check_kptr_restrict(proc_root))
        results.append(_check_host_perf_binary())

    gpu_result, has_gpu = _check_nvidia_gpu(require_gpu=check_gpu)
    results.append(gpu_result)
    results.append(_check_nvidia_toolkit(backend, has_gpu=has_gpu, require_gpu=check_gpu))
    results.append(_check_nvidia_ncu_counters(proc_root, has_gpu=has_gpu, require_gpu=check_gpu))

    return results
