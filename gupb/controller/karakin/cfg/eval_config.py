from gupb.controller import random
from gupb.controller.karakin import KarakinController

karakin_controller = KarakinController(step_no=5, is_training=False).eval()

CONFIGURATION = {
    'arenas': [
        'ordinary_chaos'
    ],
    'controllers': [
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
        karakin_controller
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    # 'visualise': True,
    # 'show_sight': karakin_controller,
    'runs_no': 100,
    'profiling_metrics': [],
}
