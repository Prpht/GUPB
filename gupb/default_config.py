from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import kirby


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
        kirby.KirbyController("Kirby")

    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': keyboard_controller,
    'runs_no': 1,
    'profiling_metrics': [],
}
