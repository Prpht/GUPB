from gupb.controller import random
from gupb.scripts import arena_generator

CONFIGURATION = {
    'arenas': arena_generator.generate_arenas(30),
    'controllers': [
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 1000,
}
