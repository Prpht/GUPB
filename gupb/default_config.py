from gupb.controller import bb_bot
from gupb.controller import botelka
from gupb.controller import claret_wolf
from gupb.controller import ihavenoideawhatimdoing
from gupb.controller import krowa123
from gupb.controller import tup_tup

CONFIGURATION = {
    'arenas': [
        'island',
    ],
    'controllers': [
        bb_bot.BBBotController("Bartek"),
        botelka.BotElkaController("Z nami na pewno zdasz"),
        ihavenoideawhatimdoing.IHaveNoIdeaWhatImDoingController(),
        tup_tup.TupTupController('Bot'),
    ],
    'visualise': True,
    'show_sight': None,
    'runs_no': 1,
}
