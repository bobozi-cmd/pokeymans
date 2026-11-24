# pokeymans

A lightweight Python pod environment builder packaged as a `.whl` with two modes:

1. **Run Mode (`run`)**: Built on top of a base Docker image from the `base-images` branch; configures `apt` packages, `pip` packages, `env`, and a service `entrypoint` during service startup/updates (defaults to **Scheme B: runtime bootstrap injection**, with **Scheme A: build-time layered image** reserved via a pluggable provisioner). Supports `debug` mode to skip the service entrypoint while keeping the full runtime environment alive.
2. **Dev Mode (`dev`)**: Uses a clean base image for **VS Code Dev Containers** without imposing service entrypoints or dependency constraints, allowing users to configure the container freely.

By default, every pod mounts `/var/log/${pod-name}` (host -> container) so service and container logs persist on the host.

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
```

## Configuration (`pokey.yaml`)

See [`examples/pokey.yaml`](examples/pokey.yaml) for a full annotated configuration reference.

## Base Images (`base-images` branch)

All official base image definitions and the master `catalog.yaml` live on the `base-images` branch of this repository. `pokey base` and `pokey up` resolve `base.name` against that branch.
