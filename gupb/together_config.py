from gupb.controller import bandyta
from gupb.controller.bb8 import bb8
from gupb.controller import berserk
from gupb.controller import ekonometron
from gupb.controller import felix_bot
from gupb.controller import funny
from gupb.controller import marwin
from gupb.controller import r2d2
from gupb.controller import wietnamczyk


CONFIGURATION = {
    'arenas': [
        'archipelago',
        'dungeon',
        'fisher_island',
    ],
    'controllers': [
        funny.FunnyController(),
        # bandyta.Bandyta("1.0"),
        wietnamczyk.WIETnamczyk(),
        berserk.BerserkBot("Ragnar"),
        r2d2.R2D2Controller("R2D2"),
        felix_bot.FelixBotController("Felix"),
        bb8.BB8Controller("BB8"),
        ekonometron.EkonometronController("Johnathan"),
        marwin.deterministic.DeterministicMarwinController("Marwin"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 500,
}
