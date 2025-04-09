import random

from math import inf
from typing import Optional

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import effects
from gupb.model import consumables
from gupb.model import weapons

from gupb.model.arenas import Arena
from gupb.model.coordinates import Coords


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

DAMAGE: dict[str, int] = {
    "land": 0,
    "sea": +inf,
    "wall": +inf,
    "forest": 0,
    "menhir": 0,
    "weaponcut": effects.CUT_DAMAGE,
    "mist": effects.MIST_DAMAGE,
    "fire": effects.FIRE_DAMAGE,
    "potion": -consumables.POTION_RESTORED_HP,
}

WEAPONS: dict[str, weapons.Weapon] = {
    "knife": weapons.Knife,
    "sword": weapons.Sword,
    "bow_loaded": weapons.Bow,
    "bow_unloaded": weapons.Bow,
    "axe": weapons.Axe,
    "amulet": weapons.Amulet,
    "scroll": weapons.Scroll,
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class ReinforcedRogueController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ReinforcedRogueController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    @property
    def name(self) -> str:
        return f"ReinforcedRogueController{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.REINFORCEDROGUE

    def praise(self, score: int) -> None:
        """For now we don't use this."""
        pass

    # =====================================================
    # =====================================================

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.terrain = Arena.load(arena_description.name).terrain
        self.damage: dict[Coords, int] = {}
        self.health = characters.CHAMPION_STARTING_HP

        for position, tile in self.terrain.items():
            self.damage[position] = DAMAGE[tile.description().type]

        self.seen: set[Coords] = set()
        self.menhir: Optional[Coords] = None

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        visible = knowledge.visible_tiles
        my_position = knowledge.position

        # --- Update health
        self.health = visible[my_position].character.health

        # --- Potential damage initialization
        potential_damage = {position: 0 for position in self.damage}

        for position, tile in visible.items():
            # --- Update `seen` set for menhir search
            if not self.menhir:
                self.seen.add(position)

            # --- See menhir?
            if tile.type == "menhir":
                self.menhir = position

            # --- Compute potential damage
            if position != my_position and tile.character:
                potential_damage[position] = +inf
                weapon = WEAPONS[tile.character.weapon.name]

                for cut_position in weapon.cut_positions(self.terrain, position, tile.character.facing):
                    potential_damage[cut_position] += DAMAGE[weapon.cut_effect().description().type]

            # --- Compute actual damage
            self.damage[position] = DAMAGE[tile.type] + sum(DAMAGE[effect.type] for effect in tile.effects)
            if tile.consumable:
                self.damage[position] += DAMAGE[tile.consumable.name]

        return random.choice(POSSIBLE_ACTIONS)


POTENTIAL_CONTROLLERS = [
    ReinforcedRogueController("Rogue"),
]
