import numpy as np
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from gupb.controller.botelka_ml.state import State, weapon_ranking_by_desc
from gupb.controller.botelka_ml.utils import debug_print
from gupb.model.characters import Action, Facing
from gupb.model.coordinates import sub_coords, Coords, add_coords


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


def find_better_weapon(grid: Grid, state: State) -> Action:
    weapons = state.weapons_info

    weapons_in_radius = [
        (coords, weapon)
        for (coords, weapon) in weapons.items()
        if abs(coords[0] - state.bot_coords[0]) < 15 and abs(coords[1] - state.bot_coords[1]) < 15
    ]

    def sorting_weapons(coords_weapon_tuple):
        return weapon_ranking_by_desc(coords_weapon_tuple[1])

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


def flee(grid: Grid, state: State) -> Action:
    enemies_in_one_line = [
        enemy_coord
        for enemy_coord in state.visible_enemies
        if enemy_coord.x == state.bot_coords.x or enemy_coord.y == state.bot_coords.y
    ]

    if len(enemies_in_one_line):
        return Action.TURN_RIGHT

    return Action.STEP_FORWARD


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
