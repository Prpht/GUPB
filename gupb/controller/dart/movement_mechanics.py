from typing import Dict, List
from pathfinding.core.grid import Grid
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder
from gupb.model.arenas import Arena, ArenaDescription, Terrain
from gupb.model.coordinates import Coords
from gupb.model.characters import Action, ChampionKnowledge, Facing
from gupb.model.tiles import TileDescription
from gupb.model.weapons import Weapon

ArenaMatrix = List[List[bool]]

TURN_ACTIONS = {
    (Facing.UP, Facing.RIGHT): Action.TURN_RIGHT,
    (Facing.UP, Facing.DOWN): Action.TURN_RIGHT,
    (Facing.UP, Facing.LEFT): Action.TURN_LEFT,
    (Facing.RIGHT, Facing.UP): Action.TURN_LEFT,
    (Facing.RIGHT, Facing.DOWN): Action.TURN_RIGHT,
    (Facing.RIGHT, Facing.LEFT): Action.TURN_RIGHT,
    (Facing.DOWN, Facing.UP): Action.TURN_LEFT,
    (Facing.DOWN, Facing.RIGHT): Action.TURN_LEFT,
    (Facing.DOWN, Facing.LEFT): Action.TURN_RIGHT,
    (Facing.LEFT, Facing.UP): Action.TURN_RIGHT,
    (Facing.LEFT, Facing.RIGHT): Action.TURN_RIGHT,
    (Facing.LEFT, Facing.DOWN): Action.TURN_LEFT
}


class MapKnowledge():
    def __init__(self, arena_description: ArenaDescription):
        self.arena = Arena.load(arena_description.name)
        self.arena_matrix = self._create_arena_matrix()
        self.arena_menhir = None
        self.weapons: Dict[Coords, str] = dict()
        self.initialize_weapons_positions()

    def _create_arena_matrix(self) -> ArenaMatrix:
        arena_matrix = [[1 for _ in range(self.arena.size[0])] for _ in range(self.arena.size[1])]
        for cords, tile in self.arena.terrain.items():
            arena_matrix[cords.y][cords.x] = 0 if tile.description().type in ['wall', 'sea'] else 1
        return arena_matrix

    def find_middle_cords(self) -> Coords:
        y = self.arena.size[0]//2
        for i in range(self.arena.size[0]//2):
            x = self.arena.size[0]//2 + i
            if self.arena_matrix[y][x]:
                return Coords(x, y)

    def find_path(self, start: Coords, end: Coords) -> List[Coords]:
        grid = Grid(matrix=self.arena_matrix)
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        start = grid.node(start.x, start.y)
        end = grid.node(end.x, end.y)
        path, _ = finder.find_path(start, end, grid)
        return path[1:]

    def initialize_weapons_positions(self) -> None:
        self.weapons = {coords:tiles.loot.description().name for coords, tiles in self.arena.terrain.items() if tiles.loot is not None}

    def update_weapons_positions(self) -> None:
        for coords in self.weapons:
            self.weapons[coords] = self.arena.terrain[coords].loot.description().name

    def get_closest_weapon_path(self, current_position: Coords, weapon_type: str) -> List[Coords]:
        weapons_coords = [coords for coords, type in self.weapons.items() if type == weapon_type]
        return self.find_shortest_path(current_position, weapons_coords)

    def find_shortest_path(self, current_position: Coords, destinations: List[Coords]) -> List[Coords]:
        paths = [self.find_path(current_position, dest) for dest in destinations]
        return min(paths, key=lambda p: len(p))


def follow_path(path: List[Coords], knowledge: ChampionKnowledge) -> Action:
    next_position = Coords(*path[0])
    current_facing = _get_facing(knowledge)
    desired_facing = _get_desired_facing(knowledge.position, next_position)
    return _determine_action(current_facing, desired_facing)


def _get_facing(knowledge: ChampionKnowledge) -> Facing:
    tile = knowledge.visible_tiles.get(knowledge.position)
    return tile.character.facing


def _get_desired_facing(current_position: Coords, desired_position: Coords) -> Facing:
    desired_facing_coordinates = desired_position - current_position
    return Facing(desired_facing_coordinates)


def _determine_action(current_facing: Facing, desired_facing: Facing) -> Action:
    if current_facing == desired_facing:
        return Action.STEP_FORWARD
    return TURN_ACTIONS[(current_facing, desired_facing)]


def is_opponent_in_front(opponent_position: Coords, visible_tiles: Dict[Coords, TileDescription]) -> bool:
    if opponent_position not in visible_tiles:
        return False
    opponent = visible_tiles[opponent_position].character
    return opponent is not None


def can_attack(terrain: Terrain,
               curren_position: Coords,
               current_facing: Facing,
               weapon: Weapon,
               opponent_position: Coords) -> bool:
    weapon_cut_positions = weapon.cut_positions(terrain, curren_position, current_facing)
    return opponent_position in weapon_cut_positions


def get_facing_for_attack(terrain: Terrain,
                          curren_position: Coords,
                          weapon: Weapon,
                          opponent_position: Coords) -> bool:
    for facing in Facing:
        if can_attack(terrain, curren_position, facing, weapon, opponent_position):
            return facing
    return None
