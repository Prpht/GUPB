from gupb.controller import bigbot
from gupb.controller import biwakspot
from gupb.controller import czak_noris
from gupb.controller import random
from gupb.controller import the_trooper
from gupb.controller.benjamin_netanyahu import BenjaminNetanyahu
from gupb.controller.jeffrey_e.jeffrey_e_controller import JeffreyEController
from gupb.controller.karakin import KarakinController
from gupb.controller.pudzian import Pudzian
from gupb.scripts import arena_generator


BASE_ARENAS = ["ordinary_chaos", "wasteland", "island", "dungeon", "archipelago"]
EVAL_GENERATED_ARENAS = 20


def _arena_pool() -> list[str]:
    generated = arena_generator.generate_arenas(EVAL_GENERATED_ARENAS)
    return BASE_ARENAS + generated


karakin_controller = KarakinController("Karakin", use_sb3=True).eval()

CONFIGURATION = {
    'arenas': _arena_pool(),
    'controllers': [
        karakin_controller,
        JeffreyEController("JeffreyE"),
        bigbot.BIGbot("BIGbot"),
        BenjaminNetanyahu("BenjaminNetanyahu"),
        biwakspot.BiwakSpot("BiwakSpot"),
        Pudzian("Pudzian"),
        czak_noris.CzakNoris("CzakNoris"),
        the_trooper.TheTrooper("TheTrooper"),
        random.RandomController("Alice"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 100,
    'profiling_metrics': [],
}
