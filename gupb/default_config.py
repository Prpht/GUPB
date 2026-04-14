from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import bigbot
from gupb.controller import bob

keyboard_controller = keyboard.KeyboardController()

CONFIGURATION = {
    'arenas': [
        'ordinary_chaos'
    ],
    'controllers': [
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
        keyboard_controller,
        bigbot.BIGbot("BIGbot"),
        bob.Bob("BobMinion"),
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': keyboard_controller,
    'runs_no': 2,
    'profiling_metrics': [],
}

