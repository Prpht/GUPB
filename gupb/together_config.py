from gupb.controller import random
from gupb.controller import benjamin_netanyahu
from gupb.controller import karakin
from gupb.controller import blade_runner
from gupb.controller import syntax_terror
from gupb.controller import jeffrey_e
from gupb.controller import bigbot
from gupb.controller import czak_noris
from gupb.controller import bob
from gupb.controller import the_trooper
from gupb.controller import pudzian
from gupb.controller import biwakspot


CONFIGURATION = {
    'arenas': [
        'ordinary_chaos'
    ],
    'controllers': [
        random.RandomController("Alice"),
        benjamin_netanyahu.BenjaminNetanyahu("BenjaminNetanyahu"),
        karakin.KarakinController("Karakin"),
        blade_runner.BladeRunner("BladeRunner"),
        syntax_terror.SyntaxTerror("Syntax Terror"),
        jeffrey_e.jeffrey_e_controller.JeffreyEController("JeffreyE"),
        bigbot.BIGbot("BIGbot"),
        czak_noris.czak_noris.CzakNoris("CzakNoris"),
        bob.Bob("BobMinion"),
        the_trooper.TheTrooper("The Trooper"),
        pudzian.Pudzian("Pudzian"),
        biwakspot.biwakspot_controller.BiwakSpot("BiwakSpot"),
    ],
    'start_balancing': False,
    'visualise': False,
    'show_sight': None,
    'runs_no': 1000,
    'profiling_metrics': [],
}
