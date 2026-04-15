from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import syntax_terror
from gupb.controller import bigbot
from gupb.controller.jeffrey_e.jeffrey_e_controller import JeffreyEController
from gupb.controller.the_trooper import TheTrooper
from gupb.controller.benjamin_netanyahu import BenjaminNetanyahu

keyboard_controller = keyboard.KeyboardController()

CONFIGURATION = {
    'arenas': [
        'ordinary_chaos'
    ],
    'controllers': [
        BenjaminNetanyahu("BenjaminNetanyahu"),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
        keyboard_controller,
        syntax_terror.SyntaxTerror("Syntax Terror"),
        # keyboard_controller,
        bigbot.BIGbot("BIGbot"),
        JeffreyEController("JeffreyE")
        TheTrooper("The Trooper"),
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': keyboard_controller,
    'runs_no': 2,
    'profiling_metrics': [],
}

