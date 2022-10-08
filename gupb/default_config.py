from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller.shrek import shrek

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
        shrek.ShrekController("Fiona")
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 5,
    'profiling_metrics': [],
}

