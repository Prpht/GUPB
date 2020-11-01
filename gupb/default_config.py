from gupb.controller import bb_bot, claret_wolf, ihavenoideawhatimdoing, shallow_mind, krowa123, tup_tup
from gupb.controller.botelka_ml.controller import BotElkaController

CONFIGURATION = {
    'arenas': [
        'fisher_island',
    ],
    'controllers': [
        bb_bot.BBBotController("Bartek"),
        BotElkaController("Z nami na pewno zdasz"),
        claret_wolf.ClaretWolfController(),
        ihavenoideawhatimdoing.IHaveNoIdeaWhatImDoingController(),
        krowa123.Krowa1233Controller("Krowka"),
        shallow_mind.ShallowMindController('test'),
        tup_tup.TupTupController('Bot'),
    ],
    'visualise': True,
    'show_sight': None,
    'runs_no': 1,
}
