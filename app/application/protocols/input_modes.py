PROTOCOL_INPUT_MODES: tuple[str, ...] = (
    "auto_pulse",
    "stack_smoothing",
    "total_target",
    "inventory_constrained",
)

WORKING_PROTOCOL_INPUT_MODES: tuple[str, ...] = (
    "auto_pulse",
    "total_target",
)

LOCKED_PROTOCOL_INPUT_MODES: tuple[str, ...] = (
    "stack_smoothing",
    "inventory_constrained",
)


def is_valid_protocol_input_mode(mode: str | None) -> bool:
    return mode in PROTOCOL_INPUT_MODES
