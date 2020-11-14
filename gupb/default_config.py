from gupb.controller.botelka_ml.controller import BotElkaController
from gupb.controller import bb_bot
from gupb.controller import claret_wolf
from gupb.controller import ihavenoideawhatimdoing
from gupb.controller import shallow_mind
from gupb.controller import krowa123
from gupb.controller import tup_tup
from gupb.controller import random

b = BotElkaController("Z nami na pewno zdasz")

CONFIGURATION = {
    'arenas': [
        'simple',
    ],
    'controllers': [b, 
        bb_bot.BBBotController("Bartek"),
        claret_wolf.ClaretWolfController(),
        ihavenoideawhatimdoing.IHaveNoIdeaWhatImDoingController(),
        krowa123.Krowa1233Controller("Krowka"),
    ],
    'visualise': False,
    'show_sight': b,
    'runs_no': 300,
}
