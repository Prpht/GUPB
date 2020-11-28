from typing import List

from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from gupb.controller.botelka_ml.wisdom import State
from gupb.model.characters import Action


def go_to_menhir(grid: Grid, state: State) -> List[Action]:
    finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
    grid.cleanup()

    start = grid.node(state.bot_coords.x, state.bot_coords.y)
    end = grid.node(state.menhir_coords.x, state.menhir_coords.y)

    path, _ = finder.find_path(start, end, grid)
    _path_to_actions(path)

    return []


def _path_to_actions(path) -> List[Action]:
    print(path)