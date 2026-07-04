"""Konfiguracja szybkiej ewaluacji Boba na wygenerowanych arenach
   python -m gupb -c gupb/controller/bob/bob_eval_config.py
"""

from gupb.controller import random as random_ctrl
from gupb.controller import czak_noris
from gupb.controller import the_trooper
from gupb.controller import biwakspot
from gupb.controller import benjamin_netanyahu
from gupb.controller import bob


def _opponents():
    """Paru lekkich przeciwnikow do ewaluacji"""
    out = []
    try:
        out.append(random_ctrl.RandomController("Alice"))
    except Exception:
        pass
    try:
        out.append(czak_noris.czak_noris.CzakNoris("CzakNoris"))
    except Exception:
        pass
    try:
        out.append(the_trooper.TheTrooper("The Trooper"))
    except Exception:
        pass
    try:
        out.append(biwakspot.biwakspot_controller.BiwakSpot("BiwakSpot"))
    except Exception:
        pass
    try:
        out.append(benjamin_netanyahu.BenjaminNetanyahu("BenjaminNetanyahu"))
    except Exception:
        pass
    return out


CONFIGURATION = {
    "arenas": [f"generated_{i}" for i in range(10)],
    "controllers": [bob.Bob("Bob")] + _opponents(),
    "start_balancing": False,
    "visualise": False,
    "show_sight": None,
    "runs_no": 30,
    "profiling_metrics": [],
}
