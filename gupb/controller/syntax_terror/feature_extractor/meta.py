import math

import numpy as np
from gupb.model import coordinates

from .constants import _DEFAULT_MIST_RADIUS, _ALIVE_COUNT_NORM, _normalize_hp
from .weapons_encoding import (
    encode_direction,
    player_weapon_one_hot,
    self_charges_norm,
)

_D_REF: float = 8.0


def _turns_to_reach(
    menhir_distance: float,
    mist_radius: float | None,
    no_of_champions_alive: int,
    mist_tick_counter: int,
) -> float:
    if menhir_distance < 1e-6:
        return 0.0
    radius = mist_radius if mist_radius is not None else _DEFAULT_MIST_RADIUS
    t_step = 2 * no_of_champions_alive
    if menhir_distance >= radius:
        return 0.0
    return max(0.0, (radius - menhir_distance) * t_step - mist_tick_counter)


def _ring_phi(
    menhir_distance: float,
    mist_radius: float | None,
    no_of_champions_alive: int,
    mist_tick_counter: int,
) -> float:
    t_step = max(1, 2 * no_of_champions_alive)
    r = mist_radius if (mist_radius is not None and mist_radius > 0) else _DEFAULT_MIST_RADIUS
    return min(1.0, menhir_distance / r + mist_tick_counter / (r * t_step))


def _ring_pressure(phi: float) -> float:
    return -math.cos(math.pi * phi)


def _observed_pressure(observed_mist_distance: float | None) -> float:
    if observed_mist_distance is None:
        return -1.0
    return math.cos(math.pi * min(1.0, observed_mist_distance / _D_REF))


def _mist_pressure(
    menhir_distance: float,
    mist_radius: float | None,
    no_of_champions_alive: int,
    mist_tick_counter: int,
    observed_mist_distance: float | None,
) -> float:
    phi = _ring_phi(menhir_distance, mist_radius, no_of_champions_alive, mist_tick_counter)
    return max(_ring_pressure(phi), _observed_pressure(observed_mist_distance))


def _encode_meta(
    menhir_distance: float,
    mist_radius: float | None,
    no_of_champions_alive: int,
    self_hp: int,
    self_weapon: str,
    mist_tick_counter: int,
    observed_mist_distance: float | None,
    menhir_pos: coordinates.Coords | None,
    start: coordinates.Coords,
    in_mist: bool,
    scroll_charges: int,
) -> np.ndarray:
    menhir_known = 1.0 if menhir_pos is not None else 0.0
    if menhir_pos is not None:
        menhir_cos, menhir_sin = encode_direction(start, menhir_pos)
    else:
        menhir_cos, menhir_sin = 0.0, 0.0

    return np.concatenate(
        (
            np.array(
                [
                    _mist_pressure(
                        menhir_distance,
                        mist_radius,
                        no_of_champions_alive,
                        mist_tick_counter,
                        observed_mist_distance,
                    ),
                    no_of_champions_alive / _ALIVE_COUNT_NORM,
                    _normalize_hp(self_hp),
                ],
                dtype=np.float32,
            ),
            player_weapon_one_hot(self_weapon),
            np.array(
                [
                    self_charges_norm(self_weapon, scroll_charges),
                    menhir_known,
                    1.0 if in_mist else 0.0,
                    menhir_cos,
                    menhir_sin,
                ],
                dtype=np.float32,
            ),
        )
    )
