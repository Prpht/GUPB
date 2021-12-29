from gupb.controller import keyboard, funny, bandyta, r2d2
from gupb.controller import random
from gupb.controller.berserk import berserk
from gupb.controller.wietnamczyk import wietnamczyk

CONFIGURATION = {
    'arenas': [
        'archipelago',
        'dungeon',
        'fisher_island',
    ],
    'controllers': [
        funny.FunnyController(),
        #bandyta.Bandyta("1.0"),
        wietnamczyk.WIETnamczyk(),
        berserk.BerserkBot("Ragnar"),
        r2d2.R2D2Controller("R2D2"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 500,
    'profiling_metrics': [],
}

