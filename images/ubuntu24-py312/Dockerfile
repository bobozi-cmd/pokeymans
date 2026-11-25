FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Core utilities, Python 3.12, and CPU observability / debugging tools
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
    && rm -rf /var/lib/apt/lists/*

# Install py-spy for low-overhead Python CPU flamegraphs (zero host-kernel version coupling)
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    py-spy

WORKDIR /workspace
