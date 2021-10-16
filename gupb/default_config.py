from gupb.controller import random
from gupb.controller import bot
from gupb.controller import keyboard

CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        bot.BotController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
        keyboard.KeyboardController(),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 20,
    'profiling_metrics': [],  # possible metrics ['all', 'total', 'avg']
}
