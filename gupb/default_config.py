from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import lord_icon

CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        lord_icon.LordIcon("Marko"),
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

