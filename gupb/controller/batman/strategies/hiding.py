from typing import Optional

from gupb.model.characters import Action
from gupb.controller.batman.navigation import Navigation
from gupb.controller.batman.passthrough import Passthrough
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


class HidingStrategy:
    def __init__(self, passthrough: Passthrough):
        self._passthrough = passthrough
        self._rooms = None
        self._current_objective = None

    def decide(self, knowledge: Knowledge, events: list[Event], navigation: Navigation) -> tuple[Optional[Action], str]:
        if knowledge.arena.menhir_position is None:
            return None, "scouting"

        # hide until we see mist close enough (10 tiles?) or the number of alive enemies has dropped to less than 5?
        if knowledge.champions_alive <= 5 or knowledge.mist_distance <= 10:
            return None, "rotating"

        for event in events:
            match event:
                case EnemyFoundEvent(enemy) if enemy.position in weapon_cut_positions(knowledge.champion, knowledge):
                    return None, "fighting"
                case ConsumableFoundEvent(consumable):
                    return None, "scouting"

        # TODO should I hide in the corner, so that no one can stab me in the back?

        pass

