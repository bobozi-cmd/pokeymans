# TODO: Finalize base image layers (apt mirrors, python tooling, non-root dev user, locales).
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# TODO: Install minimal base dependencies required by both run mode (Scheme B) and VS Code dev containers
# e.g., ca-certificates, curl, git, bash, python3, python3-pip, python3-venv, sudo
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
