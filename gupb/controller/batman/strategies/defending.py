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


class DefendingStrategy:
    def __init__(self):
        self._steps_at_current_position = 0

    def decide(self, knowledge: Knowledge, events: list[Event], navigation: Navigation) -> tuple[Action, str]:
        self._steps_at_current_position += 1

        for event in events:
            if isinstance(event, EnemyFoundEvent):
                if event.champion.position in weapon_cut_positions(knowledge):
                    return Action.ATTACK, "defending"

        # if no enemy found, but we are losing health, we should run away
        for event in events:
            if isinstance(event, LosingHealthEvent):
                return navigation.next_step(knowledge, navigation.find_closest_free_tile(knowledge)), "defending"

        if knowledge.arena.menhir_position is not None \
                and navigation.manhattan_distance(knowledge.champion.position, knowledge.arena.menhir_position) > 3:
            return navigation.next_step(knowledge, knowledge.arena.menhir_position), "scouting"

        position = navigation.find_closest_free_tile(knowledge)
        action = navigation.next_step(knowledge, position)

        if action == Action.STEP_FORWARD:
            self._steps_at_current_position = 0

        return action, "defending"
