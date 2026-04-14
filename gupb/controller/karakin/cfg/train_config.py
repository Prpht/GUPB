from gupb.controller import random
from gupb.controller.karakin import KarakinController


CONFIGURATION = {
    'arenas': [
        'ordinary_chaos'
    ],
    'controllers': [
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
        KarakinController(step_no=5, is_training=True)
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 1000,
    'profiling_metrics': [],
}
