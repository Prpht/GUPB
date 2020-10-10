from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import botelka

KEYBOARD_CONTROLLER = keyboard.KeyboardController()
BOTELKA =  botelka.BotElkaController("Elka")

CONFIGURATION = {
    'arenas': [
        'island',
    ],
    'controllers': [
        BOTELKA,
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
    ],
    'visualise': True,
    'show_sight': BOTELKA,
    'runs_no': 1,
}
