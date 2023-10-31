from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import ancymon

ancymon_controler = ancymon.AncymonController("Ancymon")

CONFIGURATION = {
    'arenas': [
        'ordinary_chaos',
    ],
    'controllers': [
        ancymon_controler,
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': ancymon_controler,
    'runs_no': 1,
    'profiling_metrics': [],
}
