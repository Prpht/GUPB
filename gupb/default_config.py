from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import kirby_learning, kirby


keyboard_controller = keyboard.KeyboardController()

CONFIGURATION = {
    'arenas': [
        'archipelago',
        'dungeon',
        'fisher_island',
        'island',
        'isolated_shrine',
        'lone_sanctum',
        'mini',
        'ordinary_chaos',
        'wasteland',
    ],
    'controllers': [
        # keyboard_controller,
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
        # kirby_learning.KirbyLearningController("KirbyLearning"),
        kirby.KirbyController("Kirby")

    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 10,  # kirby.ROUNDS_NO,
    'profiling_metrics': [],
}
