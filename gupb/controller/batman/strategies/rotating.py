from typing import Optional

from gupb.model.characters import Action
from gupb.controller.batman.navigation import Navigation
from gupb.controller.batman.strategies.scouting import weapon_cut_positions
from gupb.controller.batman.environment.knowledge import (
    Knowledge,
    ArenaKnowledge,
    TileKnowledge,
    ChampionKnowledge,
    WeaponKnowledge,
    ConsumableKnowledge
)
from gupb.controller.batman.events import (
    Event,
    MenhirFoundEvent,
    WeaponFoundEvent,
    ConsumableFoundEvent,
    LosingHealthEvent,
    EnemyFoundEvent
)


class RotatingStrategy:
    def __init__(self):
        self._current_objective = None
        self._current_objective_name = None

    def decide(self, knowledge: Knowledge, events: list[Event], navigation: Navigation) -> tuple[Optional[Action], str]:
        if knowledge.arena.menhir_position is None:
            return None, "scouting"

        if knowledge.position == knowledge.arena.menhir_position:
            return None, "defending"

        if knowledge.position == self._current_objective:
            self._current_objective = None
            self._current_objective_name = None

        if self._current_objective is None:
            self._current_objective = knowledge.arena.menhir_position
            self._current_objective_name = "menhir"

        for event in events:
            match event:
                case ConsumableFoundEvent(consumable) \
                        if navigation.manhattan_terrain_distance(consumable.position, knowledge.position) <= 5:
                    self._current_objective = consumable.position
                    self._current_objective_name = "consumable"
                case EnemyFoundEvent(enemy) if enemy.position in weapon_cut_positions(knowledge.champion, knowledge):
                    # TODO add if it is profitable depending on the mist
                    # TODO maybe return None, "fighting" but have something to go to the center instead of running away
                    return Action.ATTACK, "rotating"

        return navigation.next_step(knowledge, self._current_objective), "rotating"
