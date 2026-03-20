from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import bitbot

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
        bitgot.BIGbot("BIGbot"),                # Sonia Weiss, Stanisław Mościcki, Wojciech Maćkowiak
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': keyboard_controller,
    'runs_no': 2,
    'profiling_metrics': [],
}

