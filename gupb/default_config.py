from gupb.controller import keyboard, our
from gupb.controller import random

CONFIGURATION = {
    'arenas': [
        'lone_sanctum',
    ],
    'controllers': [
        our.OurController("OOSOS"),
        random.RandomController("Alice"),
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 5,
    'profiling_metrics': [],
}