from gupb.controller.dart.strategy import RunAwayStrategy
from .dart_controller import DartController

__all__ = [
    'DartController',
    'POTENTIAL_CONTROLLERS',
]

strategy = RunAwayStrategy()

POTENTIAL_CONTROLLERS = [
    DartController("Dart", strategy),
]
