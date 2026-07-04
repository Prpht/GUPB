from ..memory import MapMemory


class DistanceMap(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.times: dict = {}
        self.hp_lost: dict = {}
        self.parents: dict = {}


def _init_turn_cache(memory: MapMemory) -> None:
    if memory._cached_turn_tick != memory.game_tick:
        memory._cached_turn_tick = memory.game_tick
        memory._cached_attacked_cells = None
        memory._return_map_max_forward_time = 0
        memory._turn_nav = None
        memory._combat_arena_cache = {}
