from gupb.controller import bandyta
from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import bb8


CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        keyboard.KeyboardController(),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 1,
    'profiling_metrics': [],  # possible metrics ['all', 'total', 'avg']
}
