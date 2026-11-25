ARG CUDA_BASE_IMAGE=nvidia/cuda:12.6.3-devel-ubuntu24.04
FROM ${CUDA_BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=all

# Core utilities, Python 3.12, CPU observability tools, and NVIDIA Nsight CLI (nsys + ncu)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    gdb \
    git \
    htop \
    less \
    lsof \
    procps \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    strace \
    sudo \
    sysstat \
    vim \
    && (apt-get install -y --no-install-recommends cuda-nsight-systems-12-6 cuda-nsight-compute-12-6 \
        || apt-get install -y --no-install-recommends nsight-systems-cli nsight-compute) \
    && rm -rf /var/lib/apt/lists/*

# Install py-spy for Python CPU flamegraphs
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    py-spy

# Ensure nsys and ncu are on PATH regardless of CUDA toolkit install layout
ENV PATH="/usr/local/cuda/bin:${PATH}"

WORKDIR /workspace
