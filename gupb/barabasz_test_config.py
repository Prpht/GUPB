from gupb.controller import random
from gupb.controller.BenadrylowyBarabasz import barabasz

CONFIGURATION = {
    'arenas': [
        'archipelago',
        'dungeon',
        'fisher_island',
        'wasteland',
    ],
    'controllers': [
        barabasz.BarabaszController("BenadrylowyBarabasz"),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 10,
}
