# pokeymans Base Images (`base-images` branch)

This branch is the central catalog and Dockerfile repository for `pokeymans` base images.

## Layout

```text
.
├── catalog.yaml                  # Master index queried by `pokey base list/info/pull`
└── images/
    └── <image-name>/
        ├── Dockerfile            # Base image build definition
        └── meta.yaml             # Image metadata (OS, Python, tags, registry ref)
```

## How `pokeymans` uses this branch

1. `pokey base sync` fetches/updates this `base-images` branch into the local cache (`~/.cache/pokeymans/base-images`).
2. `pokey base list` / `pokey base info <name>` reads `catalog.yaml`.
3. `pokey base pull <name>` resolves `<name>` from `catalog.yaml`:
   - If `registry_ref` is set, pulls the pre-built image from the container registry.
   - Otherwise, builds locally from the referenced `Dockerfile` and tags it as `pokeymans-base/<name>:<tag>`.
