from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller.sniezny_kockodan import kockodan

CONFIGURATION = {
    'arenas': [
        'lone_sanctum',
    ],
    'controllers': [
        #keyboard.KeyboardController(),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
        kockodan.SnieznyKockodanController('Kocek'),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius")
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 5,
    'profiling_metrics': [],
}

