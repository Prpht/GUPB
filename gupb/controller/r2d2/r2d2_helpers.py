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

from .r2d2_state_machine import R2D2StateMachineV2 as R2D2StateMachine
from .utils import *


def choose_destination(arena_matrix: np.ndarray) -> Coords:
    """
    Randomly choose a destination for the champion. Decision is made based only on the arena topology,
    regardless of the visible items nor enemies. Only a Land or Menhir tiles are considered as possible destinations.
    Cannot choose a tile with the mist effect as a plausable destination.

    :param arena_matrix: the matrix representing the currently assumed arena state
    :return: destination coordinates
    """

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

    # Randomly choose a destination in np indexing format
    sample = np_coords[np.random.choice(len(np_coords))]

    # Convert np indexing format to Coords
    destination = Coords(sample[1], sample[0])

    return destination

def choose_destination_around_menhir(arena_matrix: np.ndarray, menhir_coords: Coords, radius: int) -> Coords:
    """
    Randomly choose a destination for the champion, within the radius from the menhir. Decision is made
    based only on the arena topology, regardless of the visible items nor enemies. Only a Land or
    Menhir tiles are considered as possible destinations. Cannot choose a tile with the mist effect
    as a plausable destination.

    :param arena_matrix: the matrix representing the currently assumed arena state
    :return: destination coordinates
    """

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
    np_coords = [c for c in np_coords if manhataan_distance(menhir_coords, Coords(c[1], c[0])) <= radius]

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

