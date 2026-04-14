from dataclasses import dataclass


@dataclass
class AdminRuntimeConfig:
    """Mutable runtime admin flags — ephemeral, reset on bot restart."""

    commerce_enabled: bool = True
    debug_enabled: bool = False
    pulse_engine_version: str = "v2"
    app_env: str = "dev"
    last_catalog_operation: dict[str, object] | None = None
