from gupb.controller import bb_bot
from gupb.controller import botelka_ml
from gupb.controller import claret_wolf
from gupb.controller import ihavenoideawhatimdoing
from gupb.controller import shallow_mind
from gupb.controller import krowa123
from gupb.controller import tup_tup

CONFIGURATION = {
    'arenas': [
        # 'archipelago',
        # 'wasteland',
        # 'dungeon',
        'fisher_island',
    ],
    'controllers': [
        # botelka_ml.BotElkaController("Z nami na pewno zdasz"),
        # claret_wolf.ClaretWolfController(),
        # ihavenoideawhatimdoing.IHaveNoIdeaWhatImDoingController(),
        # krowa123.Krowa1233Controller("Krowka"),
        # shallow_mind.ShallowMindController('test'),
        # tup_tup.TupTupController('Bot'),
        bb_bot.BBBotController("Bartek"),
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 1,
}
