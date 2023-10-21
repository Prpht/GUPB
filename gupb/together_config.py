from gupb.controller import random
from gupb.scripts import arena_generator

from gupb.controller import aragorn


CONFIGURATION = {
    'arenas': [
        'ordinary_chaos',
    ],
    'controllers': [
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),

        aragorn.AragornController("Aragorn"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 1000,
}
