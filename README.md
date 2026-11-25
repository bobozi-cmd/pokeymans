# pokeymans

A lightweight Python pod environment builder packaged as a `.whl` with two modes and built-in profiling support:

1. **Run Mode (`run`)**: Built on top of a base Docker image from the `base-images` branch; configures `apt` packages, `pip` packages, `env`, and a service `entrypoint` during service startup/updates (defaults to **Scheme B: runtime bootstrap injection**, with **Scheme A: build-time layered image** reserved via a pluggable provisioner). Supports `debug` mode to skip the service entrypoint while keeping the full runtime environment alive.
2. **Dev Mode (`dev`)**: Uses a clean base image for **VS Code Dev Containers** without imposing service entrypoints or dependency constraints, allowing users to configure the container freely.
3. **Built-in Perf & GPU Profiling (`perf`)**: Enabled by default in both Run and Dev modes (`SYS_PTRACE`, `PERFMON`, `seccomp=unconfined`, plus `SYS_ADMIN` & `NVIDIA_DRIVER_CAPABILITIES=all` when GPUs are attached). Pair with `ubuntu24-py312` (`py-spy`, `htop`, `sysstat`, `strace`, `gdb`) or `ubuntu24-cuda12-py312` (`nsys`, `ncu`, `py-spy`) on the `base-images` branch, and check host readiness with `pokey doctor`.

By default, every pod mounts `~/.local/state/pokeymans/logs/${pod-name}` (host) -> `/var/log/${pod-name}` (container) and sets `POKEY_PROFILE_DIR=/var/log/${pod-name}/profiles` so logs, flamegraphs, and Nsight reports persist on the host.

## Quick Build & Install (`.whl`)

```bash
python3 -m pip install --upgrade build
python3 -m build --wheel
pip install dist/pokeymans-0.1.0-py3-none-any.whl
```

## CLI Overview (`pokey`)

```text
pokey init                          # Generate pokey.yaml template
pokey up [--mode run|dev] [--debug] # Start pod environment
pokey update [--debug]              # Update running service from pokey.yaml (Run Mode)
pokey down [--mode run|dev|all]     # Stop and remove pod container(s)
pokey status [--mode run|dev|all]   # Inspect pod status & mounts
pokey logs [--mode run|dev] [-f]    # View pod logs
pokey exec [--mode run|dev] -- CMD  # Run command inside pod container

pokey dev init                      # Generate .devcontainer/devcontainer.json
pokey dev open                      # Start dev pod and open in VS Code
pokey dev snapshot <tag>            # Commit current dev container to an image
pokey dev export                    # Export installed packages to pokey.yaml snippet

pokey base sync                     # Sync base-images catalog from git `base-images` branch
pokey base list                     # List available base images
pokey base info <name>              # Show metadata for a base image
pokey base pull <name>              # Pull (or build locally) a base image from `base-images`

pokey doctor [--gpu] [--json]       # Check host Docker / perf / NVIDIA nsys & ncu readiness
```

## Configuration (`pokey.yaml`)

See [`examples/pokey.yaml`](examples/pokey.yaml) for a full annotated configuration reference.
