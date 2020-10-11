import math
import random
from typing import Dict, List, Optional

from gupb.model import arenas, coordinates, tiles, weapons
from gupb.model import characters
from gupb.model.characters import ChampionDescription, Facing
from gupb.model.coordinates import add_coords

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
        self.last_position: Optional[coordinates.Coords] = None

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
        self.last_position = None
        self.tiles = {}
        self.time = 0
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.champion = knowledge.visible_tiles[knowledge.position].character
        if self.champion is None:
            # Kind of a bug
            return random.choice(POSSIBLE_ACTIONS[:-1])
        self.position = knowledge.position
        self.tiles.update({coord: (self.time, tile_desc) for coord, tile_desc in knowledge.visible_tiles})

        if self.__mist_is_coming(knowledge.position, knowledge.visible_tiles):
            action = self.__escape_from_mist(knowledge.position, knowledge.visible_tiles)
        elif self.check_if_hit(knowledge.visible_tiles):
            action = characters.Action.ATTACK
        else:
            action = self.__find_enemy(knowledge.position, knowledge.visible_tiles)
        if action == self.last_action and knowledge.position == self.last_position:
            action = random.choice(POSSIBLE_ACTIONS[:-1])
        self.last_action = action
        self.last_position = knowledge.position
        self.time += 1
        return action

    def check_if_hit(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> bool:
        """
        Check if attack will hit someone
        """
        weapon_type = type(self.champion.weapon)
        facing = self.champion.facing
        characters_on_positions = []
        if isinstance(weapon_type, weapons.LineWeapon):
            # get positions in weapon reach
            positions = [self.position + (facing.value[0] * x, facing.value[1] * x) for x in range(1, weapon_type.reach() + 1)]
            characters_on_positions = self._get_characters_on_positions(visible_tiles, positions)
        elif isinstance(type(self.champion.weapon), weapons.Axe):
            centre_position = self.position + facing.value
            left_position = centre_position + facing.turn_left().value
            right_position = centre_position + facing.turn_right().value
            characters_on_positions = self._get_characters_on_positions(visible_tiles, [left_position, centre_position, right_position])
        elif isinstance(type(self.champion.weapon), weapons.Amulet):
            characters_on_positions = self._get_characters_on_positions(
                visible_tiles,
                [self.position + (1, 1), self.position + (-1, 1), self.position + (1, -1), self.position + (-1, -1)]
            )
        return len(characters_on_positions) > 0

    def _get_characters_on_positions(
        self,
        tiles: Dict[coordinates.Coords, tiles.TileDescription],
        positions: List[coordinates.Coords]
    ) -> List[coordinates.Coords]:
        characters_positions = []
        for position in positions:
            if position == self.position:
                continue
            tile = tiles.get(position)
            if tile and tile.character:
                characters_positions.append(position)
        return characters_positions

    @property
    def name(self) -> str:
        return f'Krowa1233Controller{self.first_name}'

    def __mist_is_coming(
        self,
        champion_position: coordinates.Coords,
        visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]
    ) -> bool:
        to_check = [
            coordinates.Coords(
                x=champion_position.x + x_d,
                y=champion_position.y + y_d
            ) for x_d in range(-2, 3, 1) for y_d in range(-2, 3, 1)
        ]
        return self.__mist_present(positions=to_check, visible_tiles=visible_tiles)

    def __mist_present(
        self,
        positions: List[coordinates.Coords],
        visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]
    ) -> bool:
        return any(
            any(e.type == "mist" for e in visible_tiles[position].effects)
            for position in positions
            if position in visible_tiles
        )

    def __escape_from_mist(
        self,
        champion_position: coordinates.Coords,
        visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]
    ) -> characters.Action:
        forward_positions = [add_coords(champion_position, self.champion.facing.value)]
        forward_positions.append(add_coords(forward_positions[-1], self.champion.facing.value))
        forward_position_is_safe = not self.__mist_present(forward_positions, visible_tiles)
        if forward_position_is_safe:
            return characters.Action.STEP_FORWARD
        return random.choice(POSSIBLE_ACTIONS[:2])

    def __find_enemy(
        self,
        champion_position: coordinates.Coords,
        visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]
    ) -> characters.Action:
        enemies = self._get_characters_on_positions(
            tiles=visible_tiles, positions=list(visible_tiles.keys())
        )
        closest_enemy = self.__find_closest_enemy(
            champion_position=champion_position, enemies_positions=enemies
        )
        if closest_enemy is None:
            return random.choice(POSSIBLE_ACTIONS[:-1])
        print(closest_enemy)
        dx, dy = int((closest_enemy[0] - champion_position[0]) > 0), int((closest_enemy[1] - champion_position[1]) > 0)
        if dx == self.champion.facing.value.x or dy == self.champion.facing.value.y:
            return characters.Action.STEP_FORWARD
        return random.choice(POSSIBLE_ACTIONS[:2])

    def __find_closest_enemy(
        self,
        champion_position: coordinates.Coords,
        enemies_positions: List[coordinates.Coords]
    ) -> Optional[coordinates.Coords]:
        if len(enemies_positions) == 0:
            return None
        distances = [
            (i, math.sqrt((e[0] - champion_position.x)**2 + (e[1] - champion_position.y)**2))
            for i, e in enumerate(enemies_positions)
        ]
        distances.sort(key=lambda d: d[1])
        return enemies_positions[distances[0][0]]


POTENTIAL_CONTROLLERS = [
    Krowa1233Controller("Krowka"),
]
