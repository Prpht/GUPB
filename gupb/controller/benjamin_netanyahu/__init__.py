from .aggressive_mode import BenjaminAggressiveMode
from .benjamin_netanyahu import BenjaminMode, BenjaminNetanyahu
from .normal_mode import BenjaminNormalMode
from .passive_mode import BenjaminPassiveMode

try:
    from .inference_mode_selector import BenjaminNetanyahuDQN
except Exception:  # pragma: no cover - keep controller discovery robust.
    BenjaminNetanyahuDQN = None

__all__ = [
    "BenjaminAggressiveMode",
    "BenjaminMode",
    "BenjaminNormalMode",
    "BenjaminNetanyahu",
    "BenjaminNetanyahuDQN",
    "BenjaminPassiveMode",
    "POTENTIAL_CONTROLLERS",
]


def _build_default_controller():
    if BenjaminNetanyahuDQN is not None:
        try:
            return BenjaminNetanyahuDQN(
                "BenjaminNetanyahu",
                mode_horizon_turns=3,
                allow_oracle_menhir=False,
            )
        except Exception:
            pass
    return BenjaminNetanyahu(
        "BenjaminNetanyahu",
        mode_horizon_turns=3,
        allow_oracle_menhir=False,
    )


POTENTIAL_CONTROLLERS = [_build_default_controller()]
