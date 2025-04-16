from gupb.controller import random
from gupb.controller.bupg import bupg
from gupb.scripts import arena_generator

CONFIGURATION = {
    'arenas': arena_generator.generate_arenas(10, arena_generator.random_size_generator()),
    'controllers': [
        bupg.BUPGController("BUPG Minion"),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': False,
    'runs_no': 100,
}
