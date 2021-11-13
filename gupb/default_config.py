from gupb.controller import keyboard
from gupb.controller import random, bandyta


CONFIGURATION = {
    'arenas': [
        'archipelago',
        'dungeon',
        'fisher_island',
    ],
    'controllers': [
        random.RandomController("Bobsd"),
        bandyta.Bandyta('k'),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius")
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 10,
    'profiling_metrics': [],  # possible metrics ['all', 'total', 'avg']
}
