from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import claret_wolf

KEYBOARD_CONTROLLER = keyboard.KeyboardController()

CONFIGURATION = {
    'arenas': [
        'island',
    ],
    'controllers': [
        KEYBOARD_CONTROLLER,
        claret_wolf.ClaretWolfController(),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
    ],
    'visualise': True,
    'show_sight': KEYBOARD_CONTROLLER,
    'runs_no': 1,
}
