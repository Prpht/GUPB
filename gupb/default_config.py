from gupb.controller import keyboard
from gupb.controller import random


CONFIGURATION = {
    'arenas': [
        'isolated_shrine',
    ],
    'controllers': [
        keyboard.KeyboardController(),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius")
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 50,
    'profiling_metrics': [],  # possible metrics ['all', 'total', 'avg']
}
