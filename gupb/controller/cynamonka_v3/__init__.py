from .cynamonka_v3 import CynamonkaController
from gupb.model.arenas import ArenaDescription
__all__ = [
    'CynamonkaController3',
    'POTENTIAL_CONTROLLERS'
]
# TODO: tu chyba przed zrobieniem PR trzeba baedzie to zmeinic
POTENTIAL_CONTROLLERS = [
    CynamonkaController("CynamonkaController3"),
]
