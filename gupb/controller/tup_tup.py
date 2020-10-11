from queue import SimpleQueue

import pygame

from gupb.model import arenas
from gupb.model import characters


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic


class TupTupController:
    def __init__(self, identifier):
        self.identifier = identifier
        self.menhir_pos = None
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TupTupController):
            return True
        return False

    def __hash__(self) -> int:
        return hash("tuptup{}".format(self.identifier))

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_pos = arena_description.menhir_position

    def decide(self,  knowledge: characters.ChampionKnowledge) -> characters.Action:
        character = knowledge.visible_tiles[knowledge.position].character
        hero_info = {'weapon': character.weapon, 'facing': character.facing}

        if self.__is_enemy_in_range():
            return characters.Action.ATTACK
        return characters.Action.DO_NOTHING

    def __is_enemy_in_range(self):
        pass

    @property
    def name(self) -> str:
        return "tuptup{}".format(self.identifier)


POTENTIAL_CONTROLLERS = [
    TupTupController('1'),
]