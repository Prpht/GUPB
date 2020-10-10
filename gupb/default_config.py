from gupb.controller import keyboard
from gupb.controller import random

KEYBOARD_CONTROLLER = keyboard.KeyboardController()

CONFIGURATION = {
    'arenas': [
        'island',
    ],
    'controllers': [
        KEYBOARD_CONTROLLER,
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
    ],
    'visualise': True,
    'show_sight': KEYBOARD_CONTROLLER,
    'runs_no': 1,
}
