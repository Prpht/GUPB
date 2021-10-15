from gupb.controller import random
from gupb.controller import bb8

CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        bb8.BB8Controller("BB8")
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 300,
    'profiling_metrics': [],  # possible metrics ['all', 'total', 'avg']
}
