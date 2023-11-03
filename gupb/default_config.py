from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller.cynamonka.cynamonka import CynamonkaController
from gupb.model.arenas import ArenaDescription

cynamonka_controller = CynamonkaController("CynamonkaController")

CONFIGURATION = {
    'arenas': [
        'ordinary_chaos',
    ],
    'controllers': [
        cynamonka_controller,
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
    'show_sight': cynamonka_controller,
    'runs_no': 10,
    'profiling_metrics': [],
}
