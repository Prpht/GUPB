from __future__ import annotations

import random

from gupb import controller
from gupb.controller.bandyta.k_bandit import K_Bandit
from gupb.controller.bandyta.tactics import passive_tactic, archer_tactic, Tactics, aggressive_tactic
from gupb.controller.bandyta.utils import POSSIBLE_ACTIONS, get_direction, find_menhir, DirectedCoords, read_arena, \
    Direction, parse_arena, \
    is_mist_coming, get_my_weapon, update_item_map, State
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import ChampionKnowledge
from gupb.model.profiling import profile


class Bandyta(controller.Controller):
    """
    Dziary na pół ryja...
    """

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.state = State(self.name)
        self.k_bandit = K_Bandit()

    def __eq__(self, other: object):
        if isinstance(other, Bandyta):
            return self.first_name == other.first_name
        return False

    def __hash__(self):
        return hash(self.first_name)

    def decide(self, knowledge: ChampionKnowledge):
        action = self.__decide(knowledge)
        return action

    def praise(self, score: int) -> None:
        self.k_bandit.learn(score)

    @profile
    def __decide(self, knowledge: ChampionKnowledge):
        try:
            self.update_state(knowledge)

            return (archer_tactic(self.state, knowledge) if self.k_bandit.tactic is Tactics.ARCHER else
                    aggressive_tactic(self.state, knowledge) if self.k_bandit.tactic is Tactics.AGGRESSIVE else
                    passive_tactic(self.state, knowledge))
        except Exception as e:
            # print(e)
            return random.choice(POSSIBLE_ACTIONS)

    def reset(self, arena_description: arenas.ArenaDescription):
        self.k_bandit.choose_tactic()
        self.state.reset()

        self.state.arena = read_arena(arena_description)
        self.state.item_map, self.state.landscape_map = parse_arena(self.state.arena)

    def update_state(self, knowledge: ChampionKnowledge):
        self.state.item_map = update_item_map(knowledge, self.state.item_map)
        direction: Direction = get_direction(knowledge)
        self.state.directed_position = DirectedCoords(knowledge.position, direction)
        self.state.weapon = get_my_weapon(knowledge.visible_tiles, self.name)
        self.state.menhir = find_menhir(knowledge.visible_tiles) if self.state.menhir is None else self.state.menhir
        self.state.mist_coming = self.state.mist_coming if self.state.mist_coming else is_mist_coming(knowledge)

    @property
    def name(self):
        return f'Bandyta{self.first_name}'

    @property
    def preferred_tabard(self):
        return characters.Tabard.GREY


POTENTIAL_CONTROLLERS = [
    Bandyta('v1.2'),
]
