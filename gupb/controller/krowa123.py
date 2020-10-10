import random
from typing import Dict, List, Optional

from gupb.model import arenas, coordinates, tiles, weapons
from gupb.model import characters
from gupb.model.characters import ChampionDescription

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Krowa1233Controller:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.tiles: Dict[coordinates.Coords, (int, tiles.TileDescription)] = {}
        self.time: int = 0
        self.menhir_position: coordinates.Coords = None
        self.champion: ChampionDescription = None
        self.position: coordinates.Coords = None
        self.last_action: characters.Action = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Krowa1233Controller):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_position = arena_description.menhir_position
        self.champion = None
        self.position = None
        self.last_action = None
        self.tiles = {}
        self.time = 0
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        action = None
        self.champion = knowledge.visible_tiles[knowledge.position].character
        self.position = knowledge.position
        self.tiles.update({coord: (self.time, tile_desc) for coord, tile_desc in knowledge.visible_tiles})

        if self.check_if_hit(knowledge.visible_tiles):
            action = characters.Action.ATTACK
        else:
            action = random.choice(POSSIBLE_ACTIONS[:-1])

        self.last_action = action
        self.time += 1
        return action

    def check_if_hit(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> bool:
        """
        Check if attack will hit someone
        """
        weapon_type = type(self.champion.weapon)
        facing = self.champion.facing
        if isinstance(weapon_type, weapons.LineWeapon):
            # get positions in weapon reach
            positions = [self.position + (facing.value[0] * x, facing.value[1] * x) for x in range(1, weapon_type.reach() + 1)]
            return self._character_present(visible_tiles, positions) is not None
        elif isinstance(type(self.champion.weapon), weapons.Axe):
            centre_position = self.position + facing.value
            left_position = centre_position + facing.turn_left().value
            right_position = centre_position + facing.turn_right().value
            return self._character_present(visible_tiles, [left_position, centre_position, right_position]) is not None
        elif isinstance(type(self.champion.weapon), weapons.Amulet):
            return self._character_present(
                visible_tiles,
                [self.position + (1, 1), self.position + (-1, 1), self.position + (1, -1), self.position + (-1, -1)]
            ) is not None
        return False

    @staticmethod
    def _character_present(tiles: Dict[coordinates.Coords, tiles.TileDescription],
                           positions: List[coordinates.Coords]) -> Optional[coordinates.Coords]:
        for position in positions:
            tile = tiles.get(position)
            if tile and tile.character:
                return position

    @property
    def name(self) -> str:
        return f'Krowa1233Controller{self.first_name}'


POTENTIAL_CONTROLLERS = [
    Krowa1233Controller("Krowka"),
]
