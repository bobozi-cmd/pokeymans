# syntax=docker/dockerfile:1
ARG CUDA_BASE_IMAGE=nvidia/cuda:12.8.1-devel-ubuntu24.04
FROM ${CUDA_BASE_IMAGE}

ARG DEBIAN_FRONTEND=noninteractive
ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
ARG TORCH_CUDA_ARCH_LIST=12.0
ARG MAX_JOBS=4

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# 1. C++/CUDA toolchain, Python 3.12, CPU perf tools, and NVIDIA Nsight CLI (nsys + ncu)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    ca-certificates \
    ccache \
    clang-format \
    clang-tidy \
    cmake \
    curl \
    g++-13 \
    gcc-13 \
    gdb \
    git \
    git-lfs \
    htop \
    less \
    locales \
    lsof \
    ninja-build \
    openssh-client \
    pkg-config \
    procps \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    strace \
    sudo \
    sysstat \
    unzip \
    vim \
    zip \
    && locale-gen en_US.UTF-8 \
    && (apt-get install -y --no-install-recommends cuda-nsight-systems-12-8 cuda-nsight-compute-12-8 \
        || apt-get install -y --no-install-recommends nsight-systems-cli nsight-compute) \
    && rm -rf /var/lib/apt/lists/*

# 2. Pre-create `dev` user (UID 1000, passwordless sudo) for VS Code Dev Mode (`dev.remote_user: dev`).
#    Keep final USER as root so Run Mode Scheme B bootstrap.sh can install apt/pip smoothly.
RUN if id ubuntu >/dev/null 2>&1; then userdel -r ubuntu; fi \
    && groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" -m -s /bin/bash "${USERNAME}" \
    && printf '%s ALL=(ALL) NOPASSWD:ALL\n' "${USERNAME}" > /etc/sudoers.d/dev \
    && chmod 0440 /etc/sudoers.d/dev

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CUDA_HOME=/usr/local/cuda \
    CC=/usr/bin/gcc-13 \
    CXX=/usr/bin/g++-13 \
    CUDAHOSTCXX=/usr/bin/g++-13 \
    TORCH_CUDA_ARCH_LIST=${TORCH_CUDA_ARCH_LIST} \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=all \
    VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:/usr/local/cuda/bin:${PATH}"

# 3. Create /opt/venv and bake heavy native/compiled ML + perf dependencies (torch cu128, triton, flash-attn, py-spy)
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir -i "${PIP_INDEX_URL}" \
        --upgrade pip setuptools wheel packaging psutil ninja \
    && /opt/venv/bin/python -m pip install --no-cache-dir \
        --index-url "${TORCH_INDEX_URL}" \
        torch==2.7.1 \
    && /opt/venv/bin/python -m pip install --no-cache-dir -i "${PIP_INDEX_URL}" \
        "triton>=3.0.0" \
        py-spy \
        ipython \
        ipykernel \
        pytest \
        debugpy \
        ruff \
        pybind11 \
    && MAX_JOBS="${MAX_JOBS}" TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST}" \
       /opt/venv/bin/python -m pip install --no-cache-dir --no-build-isolation -i "${PIP_INDEX_URL}" \
        flash-attn \
    && chown -R "${USER_UID}:${USER_GID}" /opt/venv

WORKDIR /workspace
