"""Wagi funkcji uzytecznosci Boba
"""

from __future__ import annotations

from typing import Dict, List, Tuple

PARAM_SPECS: List[Tuple[str, float, float, float]] = [
    ("attack_hit", 6.0, 0.0, 15.0),
    ("kill_opportunity", 13.0, 0.0, 30.0),
    ("engage_bonus", 4.0, 0.0, 15.0),
    ("weapon_upgrade", 5.0, 0.0, 15.0),
    ("potion", 4.0, 0.0, 15.0),
    ("low_hp_potion_multiplier", 3.0, 1.0, 8.0),
    ("critical_hp_potion_bonus", 9.0, 0.0, 30.0),
    ("menhir", 3.0, 0.0, 12.0),
    ("menhir_late_multiplier", 4.0, 1.0, 10.0),
    ("center_fallback", 3.0, 0.0, 12.0),
    ("mist_distance_bonus", 0.7, 0.0, 4.0),
    ("explore", 2.0, 0.0, 8.0),
    ("frontier_bonus", 2.0, 0.0, 8.0),
    ("building_interest", 2.0, 0.0, 8.0),
    ("door_bonus", 1.5, 0.0, 6.0),
    ("known_loot_bonus", 2.0, 0.0, 8.0),
    ("unvisited_bonus", 1.5, 0.0, 6.0),
    ("unknown_risk", 1.0, 0.0, 6.0),
    ("late_unknown_penalty", 2.0, 0.0, 10.0),
    ("visited_penalty", 0.6, 0.0, 4.0),
    ("loop_penalty", 4.0, 0.0, 15.0),
    ("blocked_penalty", 8.0, 0.0, 25.0),
    ("fire_penalty", 30.0, 0.0, 80.0),
    ("mist_penalty", 14.0, 0.0, 40.0),
    ("threat_penalty", 5.0, 0.0, 25.0),
    ("low_hp_threat_multiplier", 2.2, 1.0, 5.0),
    ("dead_end_penalty", 3.0, 0.0, 12.0),
    ("escape_route_bonus", 0.7, 0.0, 4.0),
    ("bow_distance_bonus", 2.0, 0.0, 8.0),
    ("axe_close_bonus", 2.0, 0.0, 8.0),
    ("sword_line_bonus", 2.0, 0.0, 8.0),
    ("amulet_diagonal_bonus", 1.5, 0.0, 8.0),
    ("scroll_tactical_bonus", 1.5, 0.0, 8.0),
    ("progress_weight", 1.3, 0.0, 5.0),
    ("target_distance_penalty", 1.0, 0.0, 5.0),
    ("side_step_bonus", 0.8, 0.0, 4.0),
    ("low_hp_aggression_penalty", 8.0, 0.0, 25.0),
    ("knife_aggression_penalty", 4.0, 0.0, 15.0),
    ("late_edge_penalty", 2.0, 0.0, 10.0),
    ("do_nothing_penalty", 20.0, 0.0, 60.0),
    ("useless_turn_penalty", 0.6, 0.0, 4.0),
]

PARAM_NAMES: List[str] = [name for name, _, _, _ in PARAM_SPECS]

DEFAULT_WEIGHTS: Dict[str, float] = {name: default for name, default, _, _ in PARAM_SPECS}

BOUNDS: List[Tuple[float, float]] = [(low, high) for _, _, low, high in PARAM_SPECS]

"""Do podmienienia po tuningu"""
BEST_WEIGHTS: Dict[str, float] = dict(DEFAULT_WEIGHTS)


def get_default_weights() -> Dict[str, float]:
    """Kopia domyślnych wag"""
    return dict(DEFAULT_WEIGHTS)


def merge_weights(custom_weights: Dict[str, float] | None) -> Dict[str, float]:
    """BEST_WEIGHTS z nadpisaniem wartościami z custom_weights"""
    base = dict(BEST_WEIGHTS)
    if custom_weights:
        base.update({k: float(v) for k, v in custom_weights.items() if k in base})
    return base


def merged_weights(overrides: Dict[str, float] | None) -> Dict[str, float]:
    """Alias zgodnościowy dla merge_weights"""
    return merge_weights(overrides)


def weights_from_vector(vector: List[float]) -> Dict[str, float]:
    """Wektor optymalizatora -> słownik wag wg PARAM_NAMES"""
    return {name: float(value) for name, value in zip(PARAM_NAMES, vector)}


def vector_from_weights(weights: Dict[str, float]) -> List[float]:
    """Słownik wag -> wektor w kolejności PARAM_NAMES."""
    return [float(weights.get(name, DEFAULT_WEIGHTS[name])) for name in PARAM_NAMES]
