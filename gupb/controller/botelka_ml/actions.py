from copy import deepcopy
from typing import Tuple

import numpy as np
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from gupb.controller.botelka_ml.state import State, weapon_ranking_by_desc
from gupb.controller.botelka_ml.utils import debug_print
from gupb.model.arenas import Arena
from gupb.model.characters import Action, Facing, ChampionKnowledge
from gupb.model.coordinates import sub_coords, Coords, add_coords
from gupb.model.games import MIST_TTH
from gupb.model.weapons import Bow, Axe, Sword, Knife, Amulet


def go_to_menhir(grid: Grid, state: State) -> Action:
    """
    Returns one step towards Menhir.
    """
    # We can not go to menhir directly because menhir itself is an obstacle.
    menhir_surroundings = [
        add_coords(state.menhir_coords, Facing.UP.value),
        add_coords(state.menhir_coords, Facing.RIGHT.value),
        add_coords(state.menhir_coords, Facing.DOWN.value),
        add_coords(state.menhir_coords, Facing.LEFT.value),
    ]

    for menhir_surrounding in menhir_surroundings:
        if menhir_surrounding == state.bot_coords:
            return Action.DO_NOTHING

        action = _go_to_coords(grid, state.bot_coords, state.facing, menhir_surrounding)

        if action != Action.DO_NOTHING:
            return action

    return Action.DO_NOTHING


def kill_them_all(grid: Grid, state: State) -> Action:
    def coords_dist(coords_0, coords_1):
        det = sub_coords(coords_0, coords_1)
        return np.sqrt(det.x ** 2 + det.y ** 2)

    attackable_players = [
        (coord, coords_dist(state.bot_coords, coord))
        for coord in state.weapon.cut_positions(state.arena.terrain, state.bot_coords, state.facing)
        if coord in state.visible_enemies
    ]

    if attackable_players:
        return Action.ATTACK

    visible_enemies = [
        (coord, coords_dist(state.bot_coords, coord))
        for coord in state.visible_enemies
    ]

    if not visible_enemies:
        return Action.DO_NOTHING

    # Closest enemy sorted by distance
    closest_enemy_coords, closest_enemy_dist = sorted(visible_enemies, key=lambda x: x[1])[0]

    return _go_to_coords(grid, state.bot_coords, state.facing, closest_enemy_coords)


def update_grid_on_incoming_mist(arena: Arena, grid: Grid, tick: int) -> Tuple[Grid, bool]:
    mist_on_map = False

    if tick % MIST_TTH == 0:
        arena.mist_radius -= 1 if arena.mist_radius > 0 else arena.mist_radius

        menhir_position = arena.menhir_position

        if arena.mist_radius:
            for coords in arena.terrain:
                distance = int(((coords.x - menhir_position.x) ** 2 + (coords.y - menhir_position.y) ** 2) ** 0.5)
                if distance == arena.mist_radius:
                    grid.node(coords.x, coords.y).walkable = False
                    grid.node(coords.x, coords.y).weight = 0
                    mist_on_map = True

    return grid, mist_on_map


def grid_with_players_mask(grid: Grid, knowledge: ChampionKnowledge, state: State) -> Grid:
    grid_cpy = deepcopy(grid)

    for coords, tile in knowledge.visible_tiles.items():
        if coords == state.bot_coords:
            continue

        if not tile.character:
            continue

        character = tile.character
        weapon_name = character.weapon.name
        weapon = {
            "bow": Bow(),
            "axe": Axe(),
            "sword": Sword(),
            "knife": Knife(),
            "amulet": Amulet(),
        }[weapon_name]
        coords_obj = Coords(*coords)

        # grid_cpy.node(coords_obj.x, coords_obj.y).walkable = False
        grid_cpy.node(coords_obj.x, coords_obj.y).weight = 10000

        for cut_pos in weapon.cut_positions(state.arena.terrain, coords_obj, character.facing):
            cut_pos_obj = Coords(cut_pos[0], cut_pos[1])

            # grid_cpy.node(cut_pos_obj.x, cut_pos_obj.y).walkable = False
            grid_cpy.node(cut_pos_obj.x, cut_pos_obj.y).weight = 10000
    # print(grid.grid_str())
    return grid_cpy


def update_grid_tiles_costs(knowledge: ChampionKnowledge, grid: Grid) -> Grid:
    # Updates Grid, weapons on map change with time
    for coords, tile in knowledge.visible_tiles.items():
        if not tile.loot:
            continue

        if coords == knowledge.position:
            continue

        weapon_weight = {
            "bow": 1,
            "amulet": 1,
            "sword": 4,
            "axe": 4,
            "knife": 10000,
        }[tile.loot.name]
        grid.node(*coords).weight = weapon_weight

    return grid


def find_better_weapon(grid: Grid, state: State) -> Action:
    weapons = state.weapons_info

    weapons_in_radius = [
        (coords, weapon)
        for (coords, weapon) in weapons.items()
        if abs(coords[0] - state.bot_coords[0]) < 15 and abs(coords[1] - state.bot_coords[1]) < 15
    ]

    def sorting_weapons(coords_weapon_tuple):
        return weapon_ranking_by_desc(coords_weapon_tuple[1], state.arena.name)

    weapons_in_radius.sort(key=sorting_weapons, reverse=True)

    if not weapons_in_radius:
        debug_print("No weapon visible")
        return Action.DO_NOTHING

    closest_weapon_position = weapons_in_radius[0][0]
    for (coords, _) in weapons_in_radius:
        path_len = _find_path_len(grid, state.bot_coords, coords)
        if path_len != -1 and path_len < 40:
            closest_weapon_position = coords
            break

    return _go_to_coords(grid, state.bot_coords, state.facing, closest_weapon_position)


def run_away(grid: Grid, state: State) -> Action:
    def simple_dist(bot_coords, node_coords):
        diff = sub_coords(bot_coords, node_coords)
        return np.sqrt(diff.x ** 2 + diff.y ** 2)

    grid.node(state.bot_coords.x, state.bot_coords.y).weight = 10000

    safe_blocks = sorted(
        [
            Coords(node.x, node.y)
            for nodes in grid.nodes
            for node in nodes
            if node.walkable and node.weight < 100
        ],
        key=lambda coord: simple_dist(state.bot_coords, coord)  # Sort ascending by distance
    )

    return _go_to_coords(grid, state.bot_coords, state.facing, safe_blocks[0]) if safe_blocks else Action.STEP_FORWARD


def _go_to_coords(grid: Grid, bot_coords: Coords, bot_facing: Facing, destination_coords: Coords) -> Action:
    if bot_coords == destination_coords:
        return Action.DO_NOTHING

    finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
    grid.cleanup()

    start = grid.node(bot_coords.x, bot_coords.y)
    end = grid.node(destination_coords.x, destination_coords.y)

    path, _ = finder.find_path(start, end, grid)

    if not path:
        return Action.DO_NOTHING

    current_cords, next_coords = path[0], path[1]
    desired_facing = Facing(sub_coords(next_coords, current_cords))

    return Action.STEP_FORWARD if bot_facing == desired_facing else _choose_rotation(bot_facing, desired_facing)


def _find_path_len(grid: Grid, bot_coords: Coords, destination_coords: Coords) -> int:
    finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
    grid.cleanup()

    start = grid.node(bot_coords.x, bot_coords.y)
    end = grid.node(destination_coords.x, destination_coords.y)

    path, _ = finder.find_path(start, end, grid)

    if not path:
        return -1

    return len(path)


def _choose_rotation(current_facing: Facing, desired_facing: Facing) -> Action:
    facing_left, facing_right = current_facing, current_facing

    while True:
        facing_left = facing_left.turn_left()
        facing_right = facing_right.turn_right()

        # First one that reaches 'desired_facing' is the most optimal
        if facing_left == desired_facing:
            return Action.TURN_LEFT

        if facing_right == desired_facing:
            return Action.TURN_RIGHT
