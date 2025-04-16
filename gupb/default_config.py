from gupb.controller import keyboard
from gupb.controller import random
from gupb.controller import kirby_learning, kirby
from gupb.controller import roomba
from gupb.controller.pirat import pirat
from gupb.controller import norgul
from gupb.controller.neat.kim_dzong_neat_jr import KimDzongNeatJuniorController


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
        keyboard_controller,
        pirat.PiratController("Pirat"),
        random.RandomController("Alice"),
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
        roomba.RoombaController("Roomba"),
        norgul.NorgulController("Norgul")
        kirby_learning.KirbyLearningController("KirbyLearning"),
        KimDzongNeatJuniorController(),
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': keyboard_controller,
    'runs_no': 5,
    'profiling_metrics': [],
}