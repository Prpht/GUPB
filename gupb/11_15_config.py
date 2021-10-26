from gupb.controller import bb8
from gupb.controller import ekonometron
from gupb.controller import felix_bot
from gupb.controller import marwin

CONFIGURATION = {
    'arenas': [
        'archipelago',
        'dungeon',
        'fisher_island',
    ],
    'controllers': [
        felix_bot.FelixBotController("Felix"),
        bb8.BB8Controller("BB8"),
        ekonometron.EkonometronController("Johnathan"),
        marwin.EvaderController("MarwinWise"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 1000,
    'profiling_metrics': [],
}
