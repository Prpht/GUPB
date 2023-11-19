from gupb.controller import keyboard
from gupb.controller import random

keyboard_controller = keyboard.KeyboardController()

CONFIGURATION = {
    'arenas': [
        'ordinary_chaos'
    ],
    'controllers': [
        keyboard_controller,
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
        random.RandomController("Asd"),
        random.RandomController("Bo"),
        random.RandomController("Ce"),
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': keyboard_controller,
    'runs_no': 1,
    'profiling_metrics': [],
}