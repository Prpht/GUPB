from gupb.controller import bb_bot
from gupb.controller.botelka_ml import controller as botelka
from gupb.controller import claret_wolf
from gupb.controller import ihavenoideawhatimdoing
from gupb.controller import shallow_mind
from gupb.controller import krowa123
from gupb.controller import tup_tup

CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        bb_bot.BBBotController("Bartek"),
        botelka.BotElkaController("Z nami na pewno zdasz"),
        claret_wolf.ClaretWolfController(),
        ihavenoideawhatimdoing.IHaveNoIdeaWhatImDoingController(),
        krowa123.Krowa1233Controller("Krowka"),
        shallow_mind.ShallowMindController('test'),
        tup_tup.TupTupController('Bot'),
    ],
    'start_balancing': True,
    'visualise': True,
    'show_sight': None,
    'runs_no': 1,
}
