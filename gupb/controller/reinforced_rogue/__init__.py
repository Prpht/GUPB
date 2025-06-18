from .reinforced_rogue import ReinforcedRogueController

__all__ = [
    'ReinforcedRogueController',
    'POTENTIAL_CONTROLLERS'
]

POTENTIAL_CONTROLLERS = [
    ReinforcedRogueController("Rogue"),
]