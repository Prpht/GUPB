from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import bigbot
from gupb.controller.pudzian import Pudzian

keyboard_controller = keyboard.KeyboardController()
pudzian_controller = Pudzian("Pudzian")

CONFIGURATION = {
    'arenas': [
        'ordinary_chaos'
    ],
    'controllers': [
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
        pudzian_controller,
        # keyboard_controller,
        # bigbot.BIGbot("BIGbot"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': pudzian_controller,
    'runs_no': 256,
    'profiling_metrics': [],
}

