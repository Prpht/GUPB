from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import bb_bot

KEYBOARD_CONTROLLER = keyboard.KeyboardController()

CONFIGURATION = {
    'arenas': [
        'island',
    ],
    'controllers': [
        # KEYBOARD_CONTROLLER,
        bb_bot.BBBotController("Bartek"),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Darius"),
        random.RandomController("Cecilia"),
    ],
    'visualise': False,
    # 'show_sight': KEYBOARD_CONTROLLER,
    'show_sight': bb_bot.BBBotController("Bartek"),
    'runs_no': 30,
}
