from queue import SimpleQueue

import pygame

from gupb.model import arenas
from gupb.model import characters


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class KeyboardController:
    def __init__(self):
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KeyboardController):
            return True
        return False

    def __hash__(self) -> int:
        return 42

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def decide(self,  knowledge: characters.ChampionKnowledge) -> characters.Action:
        if self.action_queue.empty():
            return characters.Action.DO_NOTHING
        else:
            return self.action_queue.get()

    def register(self, key):
        if key == pygame.K_UP:
            self.action_queue.put(characters.Action.STEP_FORWARD)
        elif key == pygame.K_DOWN:
            self.action_queue.put(characters.Action.ATTACK)
        elif key == pygame.K_LEFT:
            self.action_queue.put(characters.Action.TURN_LEFT)
        elif key == pygame.K_RIGHT:
            self.action_queue.put(characters.Action.TURN_RIGHT)

    @property
    def name(self) -> str:
        return 'KeyboardController'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE


POTENTIAL_CONTROLLERS = [
    KeyboardController(),
]
