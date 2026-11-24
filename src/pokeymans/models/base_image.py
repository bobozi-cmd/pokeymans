"""Data models representing entries from the `base-images` branch catalog."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BaseImageSpec:
    """Metadata describing one base image entry in `catalog.yaml`."""

    name: str
    tag: str = "latest"
    description: str = ""
    dockerfile: str = ""
    meta: str = ""
    registry_ref: str = ""
    os: str = ""
    python: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.name}:{self.tag}"

    @property
    def local_image_ref(self) -> str:
        """Canonical Docker image ref when built locally from the `base-images` Dockerfile."""
        return f"pokeymans-base/{self.name}:{self.tag}"

    @property
    def effective_image_ref(self) -> str:
        """Return registry_ref if published, otherwise local_image_ref."""
        return self.registry_ref or self.local_image_ref


@dataclass
class BaseImageCatalog:
    """Parsed representation of `catalog.yaml` on the `base-images` branch."""

    version: str = "1"
    branch: str = "base-images"
    images: list[BaseImageSpec] = field(default_factory=list)

    def find(self, name: str, tag: str | None = None) -> BaseImageSpec | None:
        """Find a base image entry by name and optional tag."""
        for img in self.images:
            if img.name == name and (tag is None or img.tag == tag):
                return img
        return None
