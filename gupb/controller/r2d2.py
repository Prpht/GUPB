from queue import SimpleQueue
from typing import Optional

from gupb.model import arenas, coordinates
from gupb.model import characters


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
        for i in reversed(range(1, 5)):
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
    R2D2Controller("R2D2"),
]
