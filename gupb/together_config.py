from gupb.controller import random
from gupb.controller import keyboard
from gupb.controller.mongolek import mongolek

CONFIGURATION = {
    'arenas': [
        'lone_sanctum',
    ],
    'controllers': [
        mongolek.Mongolek("Mongolek"),

    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': None,
    'runs_no': 1,
}
