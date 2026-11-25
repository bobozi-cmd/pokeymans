# pokeymans Base Images (`base-images` branch)

This branch is the central catalog and Dockerfile repository for `pokeymans` base images.

## Available Images

| Image | OS | Python | Profiling & ML Toolchain |
| :--- | :--- | :--- | :--- |
| `ubuntu24-py312:latest` | Ubuntu 24.04 | 3.12 | `py-spy`, `htop`, `sysstat`, `procps`, `strace`, `gdb` |
| `ubuntu24-cuda12-py312:latest` | Ubuntu 24.04 + CUDA 12.6 | 3.12 | CPU perf tools + `nsys` + `ncu` |
| `ubuntu24-cuda128-llm-py312:latest` | Ubuntu 24.04 + CUDA 12.8.1 (`sm_120` / Blackwell) | 3.12 (`/opt/venv`) | `torch==2.7.1+cu128`, `triton`, `flash-attn`, `nsys`, `ncu`, `py-spy`, `gcc-13`, `cmake`, `ninja` |

## Layout

```text
.
├── catalog.yaml
└── images/
    ├── ubuntu24-py312/
    ├── ubuntu24-cuda12-py312/
    └── ubuntu24-cuda128-llm-py312/
        ├── Dockerfile
        └── meta.yaml
```

## Profiling Quick Examples Inside a Pokey Pod

```bash
# Python CPU flamegraph (saved directly into persisted /var/log/${POKEY_POD_NAME}/profiles)
py-spy record -o "${POKEY_PROFILE_DIR:-/tmp}/flame.svg" --pid <PID> --duration 30

# NVIDIA Nsight Systems timeline trace (GPU base image)
nsys profile -o "${POKEY_PROFILE_DIR:-/tmp}/trace" --trace=cuda,nvtx,osrt python3 bench.py

# NVIDIA Nsight Compute kernel analysis (GPU base image)
ncu -o "${POKEY_PROFILE_DIR:-/tmp}/kernel" --set full python3 example.py
```
