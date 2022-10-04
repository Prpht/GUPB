from gupb.controller import keyboard
from gupb.controller import random


CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        keyboard.KeyboardController(),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 5,
    'profiling_metrics': [],
}

