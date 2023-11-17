from .cynamonka import CynamonkaController
from gupb.model.arenas import ArenaDescription
__all__ = [
    'CynamonkaController',
    'POTENTIAL_CONTROLLERS'
]
# TODO: tu chyba przed zrobieniem PR trzeba baedzie to zmeinic
POTENTIAL_CONTROLLERS = [
    CynamonkaController("CynamonkaController"),
]
