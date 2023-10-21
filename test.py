from gupb.controller.random import RandomController
from gupb.controller.bob.agent import FSMBot

CONFIGURATION = {
    'arenas': ['ordinary_chaos'],
    'controllers': [
        RandomController('Alice'),
        RandomController('Bob'),
        RandomController('Tim'),
        FSMBot()
    ],
    'visualise': True,
    'runs_no': 1,
    'start_balancing': False
}
