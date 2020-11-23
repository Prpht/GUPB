from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from pathfinding.core.grid import Grid
from pathfinding.finder.dijkstra import DijkstraFinder

from gupb.model.arenas import Arena
from gupb.model.characters import ChampionKnowledge, Facing
from gupb.model.coordinates import Coords, add_coords, sub_coords
from gupb.model.weapons import Weapon, Axe, Sword, Amulet, Knife, Bow

WEAPONS = {
    "bow": Bow(),
    "axe": Axe(),
    "sword": Sword(),
    "knife": Knife(),
    "amulet": Amulet(),
}

MAX_HEALTH = 5

def weapon_ranking(weapon: Weapon) -> int:
    if isinstance(weapon, Bow):
        return 10
    if isinstance(weapon, Amulet):
        return 8
    if isinstance(weapon, Axe):
        return 6
    if isinstance(weapon, Sword):
        return 6
    return 0


class DistanceMeasure(Enum):
    CLOSE = 0
    FAR = 1
    VERY_FAR = 2
    INACCESSIBLE = 3


@dataclass
class Wisdom:
    arena: Arena
    knowledge: Optional[ChampionKnowledge]
    bot_name: str
    grid: Grid
    prev_knowledge: Optional[ChampionKnowledge] = None
    finder = DijkstraFinder()
    t: int = 0 

    def next_knowledge(self, knowledge:ChampionKnowledge):
        self.prev_knowledge = self.knowledge
        self.knowledge = knowledge
        self.t += 1

    @property
    def coords_did_not_change(self):
        if not self.prev_knowledge:
            return False
        return self.knowledge.position == self.prev_knowledge.position

    @property
    def bot_coords(self) -> Coords:
        return self.knowledge.position

    @property
    def bot_facing(self) -> Facing:
        tile = self.knowledge.visible_tiles[self.bot_coords]

        assert tile.character, "Character must be standing on a tile"

        return tile.character.facing

    @property
    def bot_health(self) -> int:
        tile = self.knowledge.visible_tiles[self.bot_coords]

        assert tile.character, "Character must be standing on a tile"

        return tile.character.health

    @property
    def prev_bot_health(self) -> int:
        if not self.prev_knowledge:
            return MAX_HEALTH
        tile = self.prev_knowledge.visible_tiles[self.bot_coords]

        assert tile.character, "Character must be standing on a tile"

        return tile.character.health

    @property
    def bot_weapon(self) -> Weapon:
        tile = self.knowledge.visible_tiles[self.bot_coords]

        assert tile.character, "Character must be standing on a tile"

        weapon_name = tile.character.weapon.name

        return WEAPONS[weapon_name]

    @property
    def mist_visible(self) -> bool:
        return any(
            visible_tile
            for visible_tile in self.knowledge.visible_tiles.values()
            if "mist" in {effect.type for effect in visible_tile.effects}
        )

    @property
    def enemies_visible(self) -> bool:
        return any(
            visible_tile
            for visible_tile in self.knowledge.visible_tiles.values()
            if visible_tile.character
        )

    @property
    def better_weapon_visible(self) -> bool:
        return any(
            tile
            for tile in self.knowledge.visible_tiles.values()
            if tile.loot and weapon_ranking(WEAPONS.get(tile.loot.name)) > weapon_ranking(self.bot_weapon)
        )

    @property
    def will_pick_up_worse_weapon(self) -> bool:
        coords_in_front = add_coords(self.bot_coords, self.bot_facing.value)

        if not self.knowledge.visible_tiles[coords_in_front].loot:
            return False

        weapon_in_front = WEAPONS.get(self.knowledge.visible_tiles[coords_in_front].loot.name)

        return weapon_ranking(weapon_in_front) < weapon_ranking(self.bot_weapon)

    @property
    def can_attack_player(self) -> bool:
        return any(
            coord
            for coord in self.bot_weapon.cut_positions(self.arena.terrain, self.bot_coords, self.bot_facing)
            if self.knowledge.visible_tiles[coord].character
        )

    @property
    def distance_to_menhir(self) -> int:
        try:
            steps_num = self.find_path_len(self.arena.menhir_position)
        except Exception:
            return DistanceMeasure.INACCESSIBLE.value

        if steps_num < 30:
            return DistanceMeasure.CLOSE.value
        if steps_num < 60:
            return DistanceMeasure.FAR.value
        return DistanceMeasure.VERY_FAR.value

    @property
    def lost_health(self):
        return self.bot_health != self.prev_bot_health

    @property
    def reach_menhir_before_mist(self):
        distance = self.distance_to_menhir
        return self.arena.mist_radius/5-self.t-30 > distance


    def find_path_len(self, coords: Coords) -> int:
        steps = 0
        self.grid.cleanup()

        start = self.grid.node(self.bot_coords.x, self.bot_coords.y)
        end = self.grid.node(coords.x, coords.y)

        path, _ = self.finder.find_path(start, end, self.grid)

        facing = self.bot_facing

        for x in range(len(path) - 1):
            actions, facing = self.move_one_tile(facing, path[x], path[x + 1])
            steps += actions

        return steps

    def move_one_tile(self, starting_facing: Facing, coord_0: Coords, coord_1: Coords) -> Tuple[int, Facing]:
        exit_facing = Facing(sub_coords(coord_1, coord_0))

        # Determine what is better, turning left or turning right.
        # Builds 2 lists and compares length.
        facing_turning_left = starting_facing
        left_actions = 0
        while facing_turning_left != exit_facing:
            facing_turning_left = facing_turning_left.turn_left()
            left_actions += 1

        facing_turning_right = starting_facing
        right_actions = 1
        while facing_turning_right != exit_facing:
            facing_turning_right = facing_turning_right.turn_right()
            right_actions +=1

        actions = right_actions if left_actions > right_actions else left_actions
        actions += 1

        return actions, exit_facing
