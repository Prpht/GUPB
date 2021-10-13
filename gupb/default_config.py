from gupb.controller import random
from gupb.controller import r2d2

CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        r2d2.R2D2Controller("R2D2")
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 300,
    'profiling_metrics': [],  # possible metrics ['all', 'total', 'avg']
}
