from gupb.controller import random


CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius")
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 300,
    'profiling_metrics': [],  # possible metrics ['all', 'total', 'avg']
}
