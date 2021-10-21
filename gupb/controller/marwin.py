import math, random

from gupb.model import arenas
from gupb.model import characters
from typing import NamedTuple, Optional

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.DO_NOTHING,
]


class EvaderController:

    def __init__(self, first_name: str):
        self.first_name: str = first_name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EvaderController):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        champion = self._get_champion(knowledge)
        enemies_facing_our_way = self._scan_for_enemies(knowledge)
        if enemies_facing_our_way:
            nearest_enemy = self._calc_distance(enemies_facing_our_way)
            if nearest_enemy <= 2.0:
                action = characters.Action.ATTACK
            else:
                action = characters.Action.TURN_LEFT

        else:
            action = random.choice(POSSIBLE_ACTIONS)
        return action  # DO_NOTHING

    def _get_champion(self, knowledge: characters.ChampionKnowledge) -> characters.Champion:
        position = knowledge.position
        return knowledge.visible_tiles[position].character

    def _scan_for_enemies(self, knowledge: characters.ChampionKnowledge) -> Optional[NamedTuple]:
        tiles_in_sight = knowledge.visible_tiles
        my_position = knowledge.position
        my_character = knowledge.visible_tiles[my_position].character
        enemies_facing_our_way = []
        for tile, tile_desc in tiles_in_sight.items():
            if tile_desc.character and tile_desc.character != my_character:  ## enemy in sight
                enemies_facing_our_way.append(tile)

        return enemies_facing_our_way or None

    def _calc_distance(self, enemies) -> float:
        nearest = math.inf
        for position in enemies:
            distance = (position[0] ** 2 + position[1] ** 2) ** 0.5
            if distance < nearest:
                nearest = distance
        return nearest

    @property
    def name(self) -> str:
        return f'EvaderController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET


POTENTIAL_CONTROLLERS = [
    EvaderController("Marwin"),
]
