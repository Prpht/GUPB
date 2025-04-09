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
from gupb.model.characters import Action, Facing
from gupb.model.tiles import TileDescription


RANDOM_POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.STEP_LEFT,
    Action.STEP_RIGHT,
    # Pacifist gameplay
    # Action.ATTACK,
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
        self.arena = Arena.load(arena_description.name)
        self.visible_tiles: dict[Coords, TileDescription] = {}
        # Menhir position
        self.menhir: Optional[Coords] = None
        # Champion attributes
        self.position: Optional[Coords] = None
        self.facing: Optional[Facing] = None
        self.health: int = characters.CHAMPION_STARTING_HP
        # Damage value functions
        self.persistent_damage: dict[Coords, int] = {}
        self.potential_damage: dict[Coords, int] = {}
        # Number of steps since last seeing given tile (initially `inf`)
        self.last_seen: dict[Coords, int] = {}

        for position, tile in self.arena.terrain.items():
            self.persistent_damage[position] = DAMAGE[tile.description().type]
            self.potential_damage[position] = DAMAGE[tile.description().type]
            self.last_seen[position] = inf

    def score(self, action: Action) -> float:
        match action:
            case Action.TURN_LEFT:
                next_position = self.position
                next_facing = self.facing.turn_left()
            case Action.TURN_RIGHT:
                next_position = self.position
                next_facing = self.facing.turn_right()
            case Action.STEP_FORWARD:
                next_position = self.position + self.facing.value
                next_facing = self.facing
            case Action.STEP_LEFT:
                next_position = self.position + self.facing.turn_left().value
                next_facing = self.facing
            case Action.STEP_RIGHT:
                next_position = self.position + self.facing.turn_right().value
                next_facing = self.facing

        health_gain = self.health - self.potential_damage[next_position]
        visibility_gain = ...
        mobility_gain = ...
        menhir_gain = ...

        return health_gain

    def decide(self, knowledge: characters.ChampionKnowledge) -> Action:
        try:
            # --- Get visible tiles
            self.visible_tiles = knowledge.visible_tiles

            # --- Get champion's current attributes
            self.position = knowledge.position
            self.facing = self.visible_tiles[self.position].character.facing
            self.health = self.visible_tiles[self.position].character.health

            # --- Initialize potential damage
            self.potential_damage = self.persistent_damage.copy()

            for position, tile in self.visible_tiles.items():
                # --- Update last seen counter
                self.last_seen[position] = 0

                # --- See menhir?
                if tile.type == "menhir":
                    self.menhir = position

                # --- Update persistent damage
                self.persistent_damage[position] = DAMAGE[tile.type]

                if tile.effects:
                    self.persistent_damage[position] += sum(DAMAGE[effect.type] for effect in tile.effects)

                if tile.consumable:
                    self.persistent_damage[position] += DAMAGE[tile.consumable.name]

                # --- Update potential damage
                self.potential_damage[position] = self.persistent_damage[position]

                if tile.character and position != self.position:
                    self.potential_damage[position] = inf

                    weapon = WEAPONS[tile.character.weapon.name]
                    if weapon != "bow_unloaded":
                        for cut_position in weapon.cut_positions(self.arena.terrain, position, tile.character.facing):
                            self.potential_damage[cut_position] += DAMAGE[weapon.cut_effect().description().type]

            for position in set(self.last_seen) - set(self.visible_tiles):
                self.last_seen[position] += 1

            # ϵ-Greedy action choice (TODO: not sure if ϵ needed)
            ϵ = 0
            if random.random() < ϵ:
                action = random.choice(RANDOM_POSSIBLE_ACTIONS)
            else:
                action = max(ACTIONS, key=lambda action: (self.score(action), random.random()))

        except Exception as e:
            # Short circuit in case of failure
            action = random.choice(RANDOM_POSSIBLE_ACTIONS)

        return action


POTENTIAL_CONTROLLERS = [
    ReinforcedRogueController("Rogue"),
]
