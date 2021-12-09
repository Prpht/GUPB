from gupb.controller import keyboard
from gupb.controller import random, bandyta


CONFIGURATION = {
    'arenas': [
        'archipelago',
        'dungeon',
        'fisher_island',
    ],
    'controllers': [
        keyboard.KeyboardController(),
        bandyta.Bandyta("test"),
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
