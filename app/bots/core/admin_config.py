from dataclasses import dataclass


@dataclass
class AdminRuntimeConfig:
    """Mutable runtime admin flags — ephemeral, reset on bot restart."""

    commerce_enabled: bool = True
