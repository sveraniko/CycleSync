from app.application.protocols.pulse_engine import PulseCalculationEngine
from app.core.config import Settings


VALID_PULSE_ENGINE_VERSIONS = {"v1", "v2"}


def resolve_pulse_engine_version(settings: Settings) -> str:
    version = (settings.pulse_engine_version or "v1").lower().strip()
    return version if version in VALID_PULSE_ENGINE_VERSIONS else "v1"


def build_live_pulse_engine(settings: Settings) -> PulseCalculationEngine:
    return PulseCalculationEngine(pulse_engine_version=resolve_pulse_engine_version(settings))
