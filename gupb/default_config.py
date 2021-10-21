from gupb.controller import keyboard, bandyta
from gupb.controller import random
from gupb.controller.bandyta import Bandyta
from gupb.controller.berserk import BerserkBot
from gupb.controller.funny_controller import FunnyController
from gupb.controller.r2d2 import R2D2Controller
from gupb.controller.wietnamczyk import WIETnamczyk

CONFIGURATION = {
    'arenas': [
        'isolated_shrine',
    ],
    'controllers': [
        Bandyta('1.0'),
        WIETnamczyk(),
        R2D2Controller('R2D2'),
        FunnyController(),
        BerserkBot('Ragnar')
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 1,
    'profiling_metrics': [],  # possible metrics ['all', 'total', 'avg']
}
