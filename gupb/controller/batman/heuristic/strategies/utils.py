from gupb.model.coordinates import Coords
from gupb.controller.batman.knowledge.knowledge import ChampionKnowledge, Knowledge
from gupb.model.weapons import Knife, Sword, Axe, Bow, Amulet


WEAPON_TO_CLASS = {
    "knife": Knife,
    "sword": Sword,
    "axe": Axe,
    "bow": Bow,
    "bow_loaded": Bow,
    "bow_unloaded": Bow,
    "amulet": Amulet,
}


def weapon_cut_positions(
    champion: ChampionKnowledge, knowledge: Knowledge
) -> list[Coords]:
    weapon_class = WEAPON_TO_CLASS[champion.weapon]
    cut_positions = weapon_class.cut_positions(
        knowledge.arena.arena.terrain, champion.position, champion.facing
    )
    return cut_positions
