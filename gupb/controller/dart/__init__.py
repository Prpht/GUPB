from gupb.controller.dart.strategy import AxeAndCenterStrategy
from .dart_controller import DartController

__all__ = [
    'DartController',
    'POTENTIAL_CONTROLLERS',
]

POTENTIAL_CONTROLLERS = [
    DartController("Dart1", AxeAndCenterStrategy()),
    DartController("Dart2", AxeAndCenterStrategy()),
    DartController("Dart3", AxeAndCenterStrategy()),
]
