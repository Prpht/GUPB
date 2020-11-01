from gupb.controller import bb_bot
from gupb.controller import botelka
from gupb.controller import claret_wolf
from gupb.controller import ihavenoideawhatimdoing
from gupb.controller import krowa123
from gupb.controller import tup_tup
from gupb.controller import random

CLARET_WOLF = claret_wolf.ClaretWolfController()

CONFIGURATION = {
    'arenas': [
        'island',
    ],
    'controllers': [
        #bb_bot.BBBotController("Bartek"),
        #botelka.BotElkaController("Z nami na pewno zdasz"),
        CLARET_WOLF,
        random.RandomController("FIRST"),
        random.RandomController("SECOND")
        #ihavenoideawhatimdoing.IHaveNoIdeaWhatImDoingController(),
        #krowa123.Krowa1233Controller("Krowka"),
        #tup_tup.TupTupController('Bot'),
    ],
    'visualise': True,
    'show_sight': CLARET_WOLF,
    'runs_no': 1,
}