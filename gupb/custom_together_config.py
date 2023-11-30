from gupb.controller import alpha_gupb
from gupb.controller import ancymon
from gupb.controller import aragorn
from gupb.controller import ares
# from gupb.controller import batman
from gupb.controller import bob
from gupb.controller import cynamonka
from gupb.controller import forrest_gump
from gupb.controller import krombopulos
from gupb.controller import maly_konik
from gupb.controller import mongolek
from gupb.controller import pat_i_kot
from gupb.controller import random
from gupb.controller import roger
# from gupb.controller import reckless_roaming_dancing_druid
from gupb.scripts import arena_generator

CONFIGURATION = {
    'arenas': arena_generator.generate_arenas(1),
    'controllers': [
        alpha_gupb.AlphaGUPB("AlphaGUPB"),
        ancymon.AncymonController("Ancymon"),
        aragorn.AragornController("AragornController"),
        ares.AresController("Nike"),
        bob.FSMBot(),
        # batman.BatmanHeuristicsController('Batman'),
        cynamonka.CynamonkaController("Cynamonka"),
        forrest_gump.ForrestGumpController("Forrest Gump"),
        krombopulos.KrombopulosMichaelController(),
        maly_konik.MalyKonik("LittlePonny"),
        mongolek.Mongolek('Mongolek'),
        pat_i_kot.PatIKotController("Kot i Pat"),
        random.RandomController("Alice"),
        # reckless_roaming_dancing_druid.RecklessRoamingDancingDruid("R2D2"),
        roger.Roger('1'),
    ],
    'start_balancing': False,
    'visualise': True,
    'show_sight': ares.AresController("Nike"),
    'runs_no': 1,
}
