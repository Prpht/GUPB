from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import ancymon

ancymon_controler = ancymon.AncymonController("Ancymon")
keyboard_controler = keyboard.KeyboardController()

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
        random.RandomController("Alice2"),
        random.RandomController("Bob2"),
        random.RandomController("Cecilia2"),
        random.RandomController("Darius2"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': ancymon_controler,
    'runs_no': 100,
    'profiling_metrics': [],
}
