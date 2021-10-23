from queue import SimpleQueue
from typing import Optional

from gupb.model import arenas, coordinates
from gupb.model import characters

MENHIR_ISOLATED_SHRINE = coordinates.Coords(9, 9)


def is_safe(i, j, matrix, visited):
    if 0 <= i < len(matrix) and 0 <= j < len(matrix[0]) and matrix[i][j] == 'land' and not visited[i][j]:
        return True
    else:
        return False


class R2D2Controller:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.facing: Optional[characters.Facing] = None
        self.position: coordinates.Coords = None
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, R2D2Controller):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def parse_map(self):
        arena = arenas.Arena.load("isolated_shrine")
        map_matrix = [[None for _ in range(arena.size[0])] for _ in range(arena.size[1])]
        for coords, tile in arena.terrain.items():
            map_matrix[coords.x][coords.y] = tile.description().type
        return map_matrix

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.update_char_info(knowledge)
        if self.is_enemy_ahead(knowledge):
            return characters.Action.ATTACK
        if not self.action_queue.empty():
            return self.action_queue.get()
        if self.is_mist_ahead(knowledge):
            self.action_queue.put(characters.Action.TURN_RIGHT)
            self.action_queue.put(characters.Action.STEP_FORWARD)
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.TURN_RIGHT

    def update_char_info(self, knowledge: characters.ChampionKnowledge) -> None:
        self.position = knowledge.position
        char_description = knowledge.visible_tiles[knowledge.position].character
        self.facing = char_description.facing

    def is_mist_ahead(self, knowledge: characters.ChampionKnowledge) -> bool:
        for i in reversed(range(1, 6)):
            visible_tile = self.position
            for j in range(i):
                visible_tile = visible_tile + self.facing.value
            if visible_tile in knowledge.visible_tiles.keys():
                for e in knowledge.visible_tiles[visible_tile].effects:
                    if e.type == 'mist':
                        return True
        else:
            return False

    def is_enemy_ahead(self, knowledge: characters.ChampionKnowledge) -> bool:
        visible_tile = self.position + self.facing.value
        if knowledge.visible_tiles[visible_tile].character:
            return True
        else:
            return False

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE


POTENTIAL_CONTROLLERS = [
    R2D2Controller("R2D2")
]
