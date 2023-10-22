from .controller import BatmanController
from .heuristics_controller import BatmanHeuristicsController

__all__ = [
    # 'BatmanController',
    'BatmanHeuristicsController',
    'POTENTIAL_CONTROLLERS'
]

POTENTIAL_CONTROLLERS = [
    # BatmanController('Batman')
    BatmanHeuristicsController('Batman')
]
