from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller.cynamonka.cynamonka import CynamonkaController
from gupb.model.arenas import ArenaDescription
from gupb.scripts import arena_generator

cynamonka_controller = CynamonkaController("CynamonkaController")

CONFIGURATION = {
    'arenas': arena_generator.generate_arenas(1),
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
    'runs_no': 1,
    'profiling_metrics': [],
}