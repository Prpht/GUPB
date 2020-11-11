from gupb.controller.botelka_ml.controller import BotElkaController

b = BotElkaController("Z nami na pewno zdasz")

CONFIGURATION = {
    'arenas': [
        'simple',
    ],
    'controllers': [b] + [BotElkaController(str(i)) for i in range(4)],
    'visualise': True,
    'show_sight': b,
    'runs_no': 20,
}
