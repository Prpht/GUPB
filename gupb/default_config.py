from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller.cynamonka.cynamonka import CynamonkaController
from gupb.model.arenas import ArenaDescription

cynamonka_controller = CynamonkaController("CynamonkaController", arena_description=ArenaDescription('ordinary_chaos'))

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
        random.RandomController("Dius"),
        random.RandomController("Ace"),
        random.RandomController("Bb"),
        random.RandomController("C"),
        random.RandomController("Das"),
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': cynamonka_controller,
    'runs_no': 3,
    'profiling_metrics': [],
}
