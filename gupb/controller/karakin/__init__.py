from .karakin_controller import KarakinController
from .strategy import StrategicMode

__all__ = [
    "KarakinController",
    "StrategicMode",
    "POTENTIAL_CONTROLLERS",
]

POTENTIAL_CONTROLLERS = [
    KarakinController("Karakin", use_sb3=True),
]
