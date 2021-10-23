from gupb.controller import bb8
from gupb.controller import dragon3000
from gupb.controller import ekonometron
from gupb.controller import felix_bot
from gupb.controller import marwin

CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        felix_bot.FelixBotController("Felix"),
        bb8.BB8Controller("BB8"),
        dragon3000.Dragon3000Controller("1.0"),
        ekonometron.EkonometronController("Johnathan"),
        marwin.EvaderController("Marwin"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 500,
    'profiling_metrics': [],
}
