from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller.ares import ares_controller as ares

keyboard_controller = keyboard.KeyboardController()

CONFIGURATION = {
    'arenas': [
        'ordinary_chaos'
    ],
    'controllers': [
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Darius"),
        ares.AresController("Nike")
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': ares.AresController("Nike"),
    'runs_no': 1,
    'profiling_metrics': [],
}
