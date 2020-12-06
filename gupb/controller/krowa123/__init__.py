from .controller import Krowa1233Controller
from .big_brains.controller import Ai2Controller

__all__ = [
    "Krowa1233Controller",
    "POTENTIAL_CONTROLLERS",
]

POTENTIAL_CONTROLLERS = [
    Krowa1233Controller("Krowka"),
    Ai2Controller("Test")
]
