from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller.rodger import roger

keyboard_controller = keyboard.KeyboardController()

CONFIGURATION = {
    'arenas': [
        'ordinary_chaos'
    ],
    'controllers': [
        keyboard_controller,
        roger.Roger('1'),
        roger.Roger('1'),
        roger.Roger('1'),
        roger.Roger('1'),
        roger.Roger('1'),
        roger.Roger('1'),
        roger.Roger('1'),
        roger.Roger('1'),
        roger.Roger('1'),
        roger.Roger('1'),
        roger.Roger('1'),
        roger.Roger('1'),
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': keyboard_controller,
    'runs_no': 1,
    'profiling_metrics': [],
}