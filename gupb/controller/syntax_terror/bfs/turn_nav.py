from dataclasses import dataclass

from gupb.model import coordinates, tiles

from ..memory import MapMemory
from .cache import DistanceMap, _init_turn_cache
from .cell import compute_cell_costs
from .options import BfsCost
from .return_map import build_return_cost_map, _note_forward_times, ReturnCostMap

_UNREACHABLE = 999999


@dataclass
class TurnNavigation:
    forward: DistanceMap
    return_map: ReturnCostMap | None

    @classmethod
    def build(
        cls,
        memory: MapMemory,
        start: coordinates.Coords,
        self_hp: int,
        known_map: dict[coordinates.Coords, tiles.TileDescription],
    ) -> "TurnNavigation":
        _init_turn_cache(memory)
        forward = compute_cell_costs(start, known_map, BfsCost.full(), self_hp, memory)
        _note_forward_times(memory, forward.times)
        return_map = None
        if memory.menhir_pos is not None:
            is_omni = memory.my_weapon == "amulet" or (known_map.get(start) and any(e.type in ("mist", "fire") for e in known_map[start].effects))
            return_map = build_return_cost_map(
                start_pos=start,
                known_map=known_map,
                omnidirectional=bool(is_omni),
                self_hp=self_hp,
                memory=memory,
                forward=forward,
            )
        nav = cls(forward=forward, return_map=return_map)
        memory._turn_nav = nav
        return nav

    @classmethod
    def get(cls, memory: MapMemory) -> "TurnNavigation | None":
        return memory._turn_nav

    def nav_score(self, pos: coordinates.Coords) -> int:
        cost = self.forward.get(pos)
        if cost is None:
            return _UNREACHABLE
        if self.return_map is None:
            return cost
        start_pos = next((k for k, v in self.forward.items() if v == 0), None)
        if start_pos is not None and start_pos not in self.return_map.pos_to_idx:
            return cost
        t = self.forward.times.get(pos, 0)
        hp_lost = self.forward.hp_lost.get(pos, 0)
        return self.return_map.query(pos, None, t, hp_lost)
