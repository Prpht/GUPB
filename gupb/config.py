from gupb.controller import random
from gupb.controller import bot

BOT = bot.BotController()

CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        BOT,
        random.RandomController("Bob"),
        random.RandomController("Cecilia"),
        random.RandomController("Darius"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': BOT,
    'runs_no': 1,
    'profiling_metrics': [],  # possible metrics ['all', 'total', 'avg']
}
