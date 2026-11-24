#!/usr/bin/env bash
# Pokeymans Run Mode Runtime Bootstrap Script (Scheme B)
# Mounted into the base container and invoked as the container entrypoint.
#
# Expected runtime environment / mounted manifest:
#   POKEY_POD_NAME        - Pod name (e.g. demo-service)
#   POKEY_DEBUG           - "true" | "false" (skip service entrypoint when "true")
#   POKEY_ENTRYPOINT      - User-configured service startup command
#   POKEY_LOG_DIR         - Mounted log directory (default: /var/log/${pod-name})
#   POKEY_MANIFEST_PATH   - Path to mounted JSON/YAML runtime config (apt, pip, env, mirrors)
#
# TODO: Implement the following stages cleanly with idempotency & logging to ${POKEY_LOG_DIR}:
#   1. Load runtime env vars and persist them to /etc/profile.d/pokey_env.sh (for debug shells).
#   2. Configure apt mirror (if provided) and install configured apt packages (skip if already installed).
#   3. Configure pip index URL (if provided) and install pip packages / requirements_file.
#   4. If POKEY_DEBUG == "true":
#        log message and `exec sleep infinity` without running POKEY_ENTRYPOINT.
#   5. Otherwise:
#        `exec bash -lc "${POKEY_ENTRYPOINT}"` so PID 1 forwards SIGTERM cleanly.

set -euo pipefail

echo "[pokeymans] TODO: bootstrap.sh runtime provisioning not yet implemented." >&2
exit 1
