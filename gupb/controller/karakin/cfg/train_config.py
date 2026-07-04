from pathlib import Path

from gupb.controller import bigbot
from gupb.controller import biwakspot
from gupb.controller import czak_noris
from gupb.controller import the_trooper
from gupb.controller.benjamin_netanyahu import BenjaminNetanyahu
from gupb.controller.jeffrey_e.jeffrey_e_controller import JeffreyEController
from gupb.controller.karakin import KarakinController
from gupb.controller.pudzian import Pudzian


def _arena_pool() -> list[str]:
    base_arenas = ["ordinary_chaos", "wasteland", "island", "dungeon", "archipelago"]
    generated = [path.stem for path in sorted(Path("resources/arenas").glob("generated_*.gupb"))]
    return base_arenas + [arena for arena in generated if arena not in base_arenas]


CONFIGURATION = {
    'arenas': _arena_pool(),
    'controllers': [
        KarakinController("Karakin", use_sb3=False),
        JeffreyEController("JeffreyE"),
        bigbot.BIGbot("BIGbot"),
        BenjaminNetanyahu("BenjaminNetanyahu"),
        biwakspot.BiwakSpot("BiwakSpot"),
        Pudzian("Pudzian"),
        czak_noris.CzakNoris("CzakNoris"),
        the_trooper.TheTrooper("TheTrooper"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 200,
    'profiling_metrics': [],
}
