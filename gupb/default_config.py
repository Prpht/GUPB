from gupb.controller import random
from gupb.controller import berserk

CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
        berserk.BerserkBot('Berserk')

    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 300,
    'profiling_metrics': [],  # possible metrics ['all', 'total', 'avg']
}
