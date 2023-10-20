from gupb.controller import cynamonka
from gupb.controller import random

cynamonka_controller = cynamonka.CynamonkaController("cynamonka")

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
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': cynamonka_controller,
    'runs_no': 1,
    'profiling_metrics': [],
}
