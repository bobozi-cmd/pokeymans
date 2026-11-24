"""Exception hierarchy for pokeymans."""


class PokeyError(Exception):
    """Base exception for all pokeymans errors."""


class ConfigError(PokeyError):
    """Raised when `pokey.yaml` is missing, malformed, or fails validation."""


class BaseImageNotFoundError(PokeyError):
    """Raised when a requested base image cannot be found in the `base-images` catalog."""


class BaseImageSyncError(PokeyError):
    """Raised when syncing or reading the `base-images` branch fails."""


class ProvisionError(PokeyError):
    """Raised when provisioning a Run Mode environment (Scheme B or Scheme A) fails."""


class ContainerRuntimeError(PokeyError):
    """Raised when an underlying Docker/container runtime command fails."""
