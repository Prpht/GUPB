from gupb.controller import keyboard
from gupb.controller import random


CONFIGURATION = {
    'arenas': [
        'archipelago',
        'dungeon',
        'fisher_island',
    ],
    'controllers': [
        keyboard.KeyboardController(),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius")
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 1,
    'profiling_metrics': [],  # possible metrics ['all', 'total', 'avg']
}
