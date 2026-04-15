from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import syntax_terror
from gupb.controller import bigbot
from gupb.controller.pudzian import Pudzian
from gupb.controller import bob
from gupb.controller.jeffrey_e.jeffrey_e_controller import JeffreyEController
from gupb.controller.the_trooper import TheTrooper
from gupb.controller.benjamin_netanyahu import BenjaminNetanyahu

keyboard_controller = keyboard.KeyboardController()
pudzian_controller = Pudzian("Pudzian")

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
        pudzian_controller,
        # keyboard_controller,
        # bigbot.BIGbot("BIGbot"),
        keyboard_controller,
        syntax_terror.SyntaxTerror("Syntax Terror"),
        # keyboard_controller,
        bigbot.BIGbot("BIGbot"),
        bob.Bob("BobMinion"),
        JeffreyEController("JeffreyE")
        TheTrooper("The Trooper"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': pudzian_controller,
    'runs_no': 256,
    'profiling_metrics': [],
}

