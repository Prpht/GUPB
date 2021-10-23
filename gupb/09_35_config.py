from gupb.controller import bandyta
from gupb.controller import berserk
from gupb.controller import funny_controller
from gupb.controller import r2d2
from gupb.controller import wietnamczyk

CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        funny_controller.FunnyController(),
        bandyta.Bandyta("1.0"),
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
