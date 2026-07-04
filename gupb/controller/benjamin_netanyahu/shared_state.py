from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles


@dataclass
class BenjaminSharedState:
    last_position: Optional[coordinates.Coords] = None
    last_action: characters.Action = characters.Action.DO_NOTHING
    failed_moves: int = 0
    recent_positions: deque[coordinates.Coords] = field(default_factory=lambda: deque(maxlen=12))

    known_menhir: Optional[coordinates.Coords] = None
    arena_name: Optional[str] = None
    seen_min_x: Optional[int] = None
    seen_max_x: Optional[int] = None
    seen_min_y: Optional[int] = None
    seen_max_y: Optional[int] = None

    known_passable: set[coordinates.Coords] = field(default_factory=set)
    known_blocked: set[coordinates.Coords] = field(default_factory=set)
    visited_count: dict[coordinates.Coords, int] = field(default_factory=lambda: defaultdict(int))
    enemy_memory: dict[str, tuple[coordinates.Coords, int]] = field(default_factory=dict)

    turn_no: int = 0
    last_hp: Optional[int] = None
    recent_damage: deque[int] = field(default_factory=lambda: deque(maxlen=4))
    panic_turns: int = 0


@dataclass(frozen=True)
class TurnContext:
    knowledge: characters.ChampionKnowledge
    current_tile: Optional[tiles.TileDescription]
    facing: characters.Facing
    current_weapon: str
    current_hp: int
    visible_enemy_positions: list[coordinates.Coords]
    enemy_positions: list[coordinates.Coords]
    mist_positions: list[coordinates.Coords]
    mist_visible: bool
