import numpy as np

from gupb.model import coordinates

from ..feature_extractor import (
    _MAX_NEAREST_ITEMS,
    _MAX_NEAREST_PLAYERS,
    player_hp_index,
    extract_features as build_feature_vector,
)
from ..tactics import has_safe_exploration_targets, menhir_reachable
from ..memory import MapMemory
from .constants import MASK_DISABLED, OUTPUT_ENEMY_BASE, OUTPUT_EXPLORE, OUTPUT_MENHIR, OUTPUT_ESCAPE_BASE, NUM_NN_OUTPUTS
from .context import TurnContext


def extract_features(ctx: TurnContext) -> np.ndarray:
    return build_feature_vector(
        ctx.memory.map_data,
        ctx.distances,
        ctx.knowledge.position,
        ctx.knowledge.no_of_champions_alive,
        ctx.hp,
        ctx.weapon,
        ctx.memory.mist_radius,
        ctx.memory.menhir_pos,
        ctx.memory.mist_tick_counter,
        ctx.memory,
    )


def get_available_actions_mask(
    features: np.ndarray,
    memory: MapMemory,
    distances: dict,
    position: coordinates.Coords,
    outputs: np.ndarray | None = None,
) -> np.ndarray:
    mask = np.ones(NUM_NN_OUTPUTS, dtype=bool)
    snapshot = memory._turn_extract_snapshot
    item_entries = snapshot["items"] if snapshot is not None else []

    for i in range(_MAX_NEAREST_ITEMS):
        if i >= len(item_entries):
            mask[i] = False

    for i in range(_MAX_NEAREST_PLAYERS):
        hp = features[player_hp_index(i)]
        if hp == 0.0:
            mask[OUTPUT_ENEMY_BASE + i] = False
            mask[OUTPUT_ESCAPE_BASE + i] = False
        elif (
            i < len(memory.last_extracted_players)
            and not memory.firing_positions_exist.get(
                memory.last_extracted_players[i], False
            )
        ):
            mask[OUTPUT_ENEMY_BASE + i] = False

    if not menhir_reachable(memory, position, distances):
        mask[OUTPUT_MENHIR] = False

    if not has_safe_exploration_targets(memory, distances):
        mask[OUTPUT_EXPLORE] = False

    return mask


def mask_invalid_outputs(
    scores: np.ndarray,
    features: np.ndarray,
    memory: MapMemory,
    distances: dict,
    outputs: np.ndarray,
    position: coordinates.Coords,
) -> np.ndarray:
    mask = get_available_actions_mask(features, memory, distances, position, outputs)
    masked = scores.copy()
    masked[~mask] = MASK_DISABLED
    return masked
