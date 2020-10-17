from gupb.controller import bb_bot
from gupb.controller import botelka
from gupb.controller import claret_wolf
from gupb.controller import ihavenoideawhatimdoing
from gupb.controller import krowa123
from gupb.controller import tup_tup

b = botelka.BotElkaController("Z nami na pewno zdasz")

CONFIGURATION = {
    'arenas': [
        'island',
    ],
    'controllers': [
        # bb_bot.BBBotController("Bartek"),
        b,
        # claret_wolf.ClaretWolfController(),
        # ihavenoideawhatimdoing.IHaveNoIdeaWhatImDoingController(),
        krowa123.Krowa1233Controller("Krowka"),
        # tup_tup.TupTupController('Bot'),
    ],
    'visualise': True,
    'show_sight': b,
    'runs_no': 1,
}
