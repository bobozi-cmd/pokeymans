# pokeymans Base Images (`base-images` branch)

This branch is the central catalog and Dockerfile repository for `pokeymans` base images.

## Available Images

| Image | OS | Python | Profiling / Perf Toolchain |
| :--- | :--- | :--- | :--- |
| `ubuntu24-py312:latest` | Ubuntu 24.04 | 3.12 | `py-spy`, `htop`, `sysstat` (`mpstat`/`iostat`), `procps`, `strace`, `gdb` |
| `ubuntu24-cuda12-py312:latest` | Ubuntu 24.04 + CUDA 12.6 | 3.12 | All CPU perf tools + NVIDIA `nsys` (Nsight Systems) + `ncu` (Nsight Compute) |

## Layout

```text
.
├── catalog.yaml                        # Master index queried by `pokey base list/info/pull`
└── images/
    ├── ubuntu24-py312/
    │   ├── Dockerfile
    │   └── meta.yaml
    └── ubuntu24-cuda12-py312/
        ├── Dockerfile
        └── meta.yaml
```

## Profiling Quick Examples Inside a Pokey Pod

```bash
# Python CPU flamegraph (saved directly into persisted /var/log/${POKEY_POD_NAME}/profiles)
py-spy record -o "${POKEY_PROFILE_DIR:-/tmp}/flame.svg" --pid <PID> --duration 30

# NVIDIA Nsight Systems timeline trace (GPU base image)
nsys profile -o "${POKEY_PROFILE_DIR:-/tmp}/trace" --trace=cuda,nvtx,osrt <command>

# NVIDIA Nsight Compute kernel analysis (GPU base image)
ncu -o "${POKEY_PROFILE_DIR:-/tmp}/kernel" --set full <command>
```
