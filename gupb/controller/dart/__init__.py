from gupb.controller.dart.strategy import AxeAndCenterStrategy
from .dart_controller import DartController

__all__ = [
    'DartController',
    'POTENTIAL_CONTROLLERS',
]

POTENTIAL_CONTROLLERS = [
    DartController("Dart", AxeAndCenterStrategy()),
]
