from .knife import Knife
from .axe import Axe
from .bow_loaded import BowLoaded
from .bow_unloaded import BowUnloaded
from .sword import Sword
from .amulet import Amulet


ALL_WEAPONS = {
    Knife.name: Knife,
    Axe.name: Axe,
    BowLoaded.name: BowLoaded,
    BowUnloaded.name: BowUnloaded,
    Sword.name: Sword,
    Amulet.name: Amulet
}
