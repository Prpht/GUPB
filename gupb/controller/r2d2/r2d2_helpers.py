from typing import Optional, Tuple

import numpy as np
from pathfinding.finder.bi_a_star import BiAStarFinder
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords

from gupb.controller.r2d2.knowledge import R2D2Knowledge
from .r2d2_state_machine import R2D2StateMachine
from .utils import *


def walking_distance(start: Coords, end: Coords, matrix_walkable: np.ndarray) -> int:

    grid = Grid(matrix=matrix_walkable)
    finder = BiAStarFinder(diagonal_movement=DiagonalMovement.never)
    path, _ = finder.find_path(grid.node(*start), grid.node(*end), grid)

    return len(path) - 1


def scan_for_items(knowledge: R2D2Knowledge, distance: int = 1000) -> Optional[Coords]:
    """
    Scan for items in the visible tiles. If there are more than one, choose acord to the items ranking.
    If there are no items in the visible tiles, return None.

    :param knowledge: the knowledge of the champion
    :return: coordinates of the closest item or None
    """

    item_tiles = []
    for coords, tile_description in knowledge.champion_knowledge.visible_tiles.items():

        # If the tile is the one the champion is standing on, ignore it
        if coords == knowledge.champion_knowledge.position:
            continue

        # Interested in weapons that are stronger than the current one
        if tile_description.loot is not None:
            if items_ranking[tile_description.loot.name] < items_ranking[knowledge.current_weapon]:
                if knowledge.world_state.menhir_position is None:
                    item_tiles.append((coords, tile_description.loot.name))
                elif walking_distance(coords, knowledge.world_state.menhir_position, knowledge.world_state.matrix_walkable) <= distance:
                    item_tiles.append((coords, tile_description.loot.name))
        
        # Always interested in consumables
        if tile_description.consumable is not None:
            item_tiles.append((coords, tile_description.consumable.name))
    
    if len(item_tiles) == 0:
        return None
    
    # Sort the items by the ranking
    item_tiles.sort(key=lambda item: items_ranking[item[1]])

    # Return the coordinates of the most valuable item
    return item_tiles[0][0]

def choose_destination(arena_matrix: np.ndarray, explored: Optional[np.ndarray] = None) -> Coords:
    """
    Randomly choose a destination for the champion. Decision is made based only on the arena topology and the explored
    matrix, regardless of the visible items nor enemies. Only a Land or Menhir tiles are considered as possible
    destinations. Cannot choose a tile with the mist effect as a plausable destination.

    :param arena_matrix: the matrix representing the currently assumed arena state
    :return: destination coordinates
    """

    xs, ys = np.where(
        (arena_matrix == tiles_mapping["land"])         |
        (arena_matrix == tiles_mapping["menhir"])       |
        (arena_matrix == tiles_mapping["knife"])        |
        (arena_matrix == tiles_mapping["sword"])        |
        (arena_matrix == tiles_mapping["bow_unloaded"]) |
        (arena_matrix == tiles_mapping["axe"])          |
        (arena_matrix == tiles_mapping["amulet"])       |
        (arena_matrix == tiles_mapping["potion"])
    )

    # The list of possible coordinates in np indexing format
    np_coords = list(zip(xs, ys))

    # Filter out the coordinates that are explored
    # - if every tile is explored, than ignore this filter
    if explored is not None:
        np_coords_filterd = [c for c in np_coords if not explored[c[0], c[1]]]
        np_coords = np_coords_filterd if len(np_coords_filterd) > 0 else np_coords

    # Randomly choose a destination in np indexing format
    sample = np_coords[np.random.choice(len(np_coords))]

    # Convert np indexing format to Coords
    destination = Coords(sample[1], sample[0])

    return destination

def choose_destination_around_menhir(knowledge: R2D2Knowledge, menhir_coords: Coords, distance: int) -> Coords:
    """
    Randomly choose a destination for the champion, within the radius from the menhir. Decision is made
    based only on the arena topology, regardless of the visible items nor enemies. Only a Land or
    Menhir tiles are considered as possible destinations. Cannot choose a tile with the mist effect
    as a plausable destination.
    """

    arena_matrix = knowledge.world_state.matrix
    walkable_matrix = knowledge.world_state.matrix_walkable

    xs, ys = np.where(
        (arena_matrix == 1) |   # Land
        (arena_matrix == 4) |   # Menhir
        (arena_matrix == 6) |   # Knife
        (arena_matrix == 7) |   # Sword
        (arena_matrix == 8) |   # Bow
        (arena_matrix == 9) |   # Axe
        (arena_matrix == 10) |  # Amulet
        (arena_matrix == 11)    # Potion
    )

    # The list of possible coordinates in np indexing format
    np_coords = list(zip(xs, ys))

    # Filter out the coordinates that are too far from the menhir
    np_coords = [c for c in np_coords if walking_distance(menhir_coords, Coords(c[1], c[0]), walkable_matrix) <= distance]

    # Randomly choose a destination in np indexing format
    sample = np_coords[np.random.choice(len(np_coords))]

    # Convert np indexing format to Coords
    destination = Coords(sample[1], sample[0])

    return destination

def scan_for_weapons(arena_matrix: np.ndarray) -> Optional[Tuple[Coords, str]]:
    """
    Scan for weapons in the visible tiles. If there are any, return the coordinates of the random one.
    If there are no weapons in the visible tiles, return None.

    :param srena_matrix: the matrix representing the currently assumed arena state
    :return: coordinates of the closest weapon or None
    """

    xs, ys = np.where(
        (arena_matrix == 6) |   # Knife
        (arena_matrix == 7) |   # Sword
        # (arena_matrix == 8) |   # Bow TODO: uncomment when bow is implemented
        (arena_matrix == 9) |   # Axe
        (arena_matrix == 10)    # Amulet
    )

    # The list of possible coordinates in np indexing format
    np_coords = list(zip(xs, ys))

    if len(np_coords) == 0:
        return None

    # Randomly choose a weapon in np indexing format
    sample = np_coords[np.random.choice(len(np_coords))]

    # Convert np indexing format to Coords
    weapon_coords = Coords(sample[1], sample[0])

    return weapon_coords, weapon_translate[arena_matrix[sample[0], sample[1]]]

