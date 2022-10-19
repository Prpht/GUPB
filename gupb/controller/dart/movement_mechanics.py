import math
from typing import Dict, List, Optional
from pathfinding.core.grid import Grid
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder
from gupb.model.arenas import FIXED_MENHIRS, Arena, ArenaDescription
from gupb.model.coordinates import Coords
from gupb.model.characters import Action, ChampionDescription, ChampionKnowledge, Facing
from gupb.model.tiles import Tile, TileDescription
from gupb.model.weapons import Amulet, Axe, Bow, Knife, Sword, Weapon

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
        self.mist_coord: Optional[Coords] = None
        self.opponents: Dict[str, Coords] = dict()

    def _create_arena_matrix(self) -> ArenaMatrix:
        arena_matrix = [[1 for _ in range(self.arena.size[0])] for _ in range(self.arena.size[1])]
        for cords, tile in self.arena.terrain.items():
            arena_matrix[cords.y][cords.x] = 0 if tile.description().type in ['wall', 'sea'] else 1
        return arena_matrix

    def find_middle_cords(self) -> Coords:
        if self.arena.name in FIXED_MENHIRS:
            return FIXED_MENHIRS[self.arena.name]
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
        self.weapons = {coords: tile.loot.description().name
                        for coords, tile in self.arena.terrain.items() if tile.loot is not None}

    def update_weapons_positions(self) -> None:
        for coords in self.weapons:
            self.weapons[coords] = self.arena.terrain[coords].loot.description().name

    def get_closest_weapon_path(self, current_position: Coords, *weapon_types: str) -> List[Coords]:
        weapons_coords = [coords for coords, type in self.weapons.items() if type.startswith(weapon_types)]
        return self.find_shortest_path(current_position, weapons_coords)

    def find_shortest_path(self, current_position: Coords, destinations: List[Coords]) -> List[Coords]:
        paths = [self.find_path(current_position, dest) for dest in destinations]
        return min(paths, key=lambda p: len(p))

    def find_closest_coords(self, current_position: Coords, destinations: List[Coords]) -> Coords:
        return min(destinations, key=lambda dest: len(self.find_path(current_position, dest)))

    def can_attack(self, knowledge: ChampionKnowledge, opponent_position: Coords) -> bool:
        weapon = get_weapon(get_champion_weapon(knowledge))
        facing = get_facing(knowledge)
        weapon_cut_positions = weapon.cut_positions(self.arena.terrain, knowledge.position, facing)
        return opponent_position in weapon_cut_positions

    def get_facing_for_attack(self, knowledge: ChampionKnowledge, opponent_position: Coords) -> Optional[Facing]:
        for facing in Facing:
            if self.can_attack(knowledge, opponent_position):
                return facing
        return None

    def is_land(self, coords: Coords) -> bool:
        return self.arena_matrix[coords.y][coords.x]

    def find_mist_coords(self, knowledge: ChampionKnowledge) -> Optional[Coords]:
        mist_coords = [Coords(*coords) for coords, tile in knowledge.visible_tiles.items() if is_mist(tile)]
        mist_coords_and_distances = [(coords, euclidean_distance(knowledge.position, coords)) for coords in mist_coords]
        return min(mist_coords_and_distances, key=lambda x: x[1])[0] if mist_coords_and_distances else None





def follow_path(path: List[Coords], knowledge: ChampionKnowledge) -> Action:
    next_position = Coords(*path[0])
    current_facing = get_facing(knowledge)
    desired_facing = get_desired_facing(knowledge.position, next_position)
    return determine_action(current_facing, desired_facing)


def get_facing(knowledge: ChampionKnowledge) -> Facing:
    tile = knowledge.visible_tiles.get(knowledge.position)
    return tile.character.facing


def get_desired_facing(current_position: Coords, desired_position: Coords) -> Facing:
    desired_facing_coordinates = desired_position - current_position
    return Facing(desired_facing_coordinates)


def determine_action(current_facing: Facing, desired_facing: Facing) -> Action:
    if current_facing == desired_facing:
        return Action.STEP_FORWARD
    return TURN_ACTIONS[(current_facing, desired_facing)]


def is_opponent_in_front(opponent_position: Coords, visible_tiles: Dict[Coords, TileDescription]) -> bool:
    if opponent_position not in visible_tiles:
        return False
    opponent = visible_tiles[opponent_position].character
    return is_opponent(opponent)


def is_opponent(character: ChampionDescription) -> bool:
    return not (character is None or character.controller_name.startswith("DartController"))


def is_mist(tile: Tile) -> bool:
    return "mist" in [e.type for e in tile.effects]

def is_menhir(tile: TileDescription) -> bool:
    return "menhir" == tile.type


def get_champion_weapon(knowledge: ChampionKnowledge) -> str:
    return knowledge.visible_tiles[knowledge.position].character.weapon.name


def get_weapon(weapon_name: str) -> Weapon:
    if weapon_name == "knife":
        return Knife()
    if weapon_name == "sword":
        return Sword()
    if weapon_name.startswith("bow"):
        return Bow()
    if weapon_name == "axe":
        return Axe()
    if weapon_name == "amulet":
        return Amulet()

def euclidean_distance(c1: Coords, c2: Coords) -> float:
    return math.sqrt((c1.x - c2.x)**2 + (c1.y - c2.y)**2)
