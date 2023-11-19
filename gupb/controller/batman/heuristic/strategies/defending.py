from typing import Optional
from operator import itemgetter
import random

from gupb.model.characters import Action

from gupb.controller.batman.heuristic.navigation import Navigation
from gupb.controller.batman.heuristic.strategies.scouting import weapon_cut_positions
from gupb.controller.batman.heuristic.events import (
    Event,
    MenhirFoundEvent,
    WeaponFoundEvent,
    ConsumableFoundEvent,
    LosingHealthEvent,
    EnemyFoundEvent,
    IdlePenaltyEvent,
)


from gupb.controller.batman.knowledge.knowledge import (
    Knowledge,
    ArenaKnowledge,
    TileKnowledge,
    ChampionKnowledge,
    WeaponKnowledge,
    ConsumableKnowledge,
)


class DefendingStrategy:
    def __init__(self):
        pass

    def decide(
        self, knowledge: Knowledge, events: list[Event], navigation: Navigation
    ) -> tuple[Optional[Action], str]:
        possible_reactions = []
        for event in events:
            reaction = None
            match event:
                case EnemyFoundEvent(
                    enemy
                ) if knowledge.position in weapon_cut_positions(
                    enemy, knowledge
                ) or enemy.position in weapon_cut_positions(
                    knowledge.champion, knowledge
                ):
                    reaction = 0, None, "fighting"
                # not seeing an enemy close enough and being attacked by multiple enemies
                case LosingHealthEvent(damage) if damage > 2:
                    reaction = 1, None, "running_away"
                # not seeing an enemy close enough and being attacked
                case LosingHealthEvent(damage):
                    # TODO would be nice to turn to the more probable side (by number of enemies, terrain, etc)
                    reaction = 2, Action.TURN_RIGHT, "defending"
                case ConsumableFoundEvent(
                    consumable
                ) if knowledge.mist_distance >= 15 or navigation.manhattan_terrain_distance(
                    consumable.position, knowledge.position
                ) <= 5:
                    reaction = 3, None, "scouting"  # collect the consumable
                case IdlePenaltyEvent(episodes_to_penalty) if episodes_to_penalty <= 2:
                    reaction = (
                        4,
                        random.choice([Action.TURN_RIGHT, Action.TURN_LEFT]),
                        "defending",
                    )
                case EnemyFoundEvent(enemy) if navigation.is_headed_towards(
                    enemy, knowledge.position
                ) and navigation.manhattan_terrain_distance(
                    enemy.position, knowledge.position
                ) <= 2:
                    direction_towards_enemy = navigation.direction_to(
                        knowledge.position, enemy.position
                    )
                    turn_action = navigation.turn(
                        knowledge.champion.facing, direction_towards_enemy
                    )
                    if turn_action is not None:
                        reaction = 5, turn_action, "defending"
                    else:
                        reaction = 5, Action.DO_NOTHING, "defending"

            if reaction is not None:
                possible_reactions.append(reaction)

        if possible_reactions:
            best_reaction = min(possible_reactions, key=itemgetter(0))
            return best_reaction[1:]

        if (
            knowledge.arena.menhir_position is not None
            and navigation.manhattan_distance(
                knowledge.position, knowledge.arena.menhir_position
            )
            > 3
        ):
            return (
                navigation.next_step(knowledge, knowledge.arena.menhir_position),
                "rotating",
            )

        if random.random() < 0.9:
            # TODO turn to where the enemy is most likely to come from?
            # TODO what if we are in an empty room? then simply guard the entrance?
            action = Action.TURN_RIGHT
        else:
            position = navigation.find_closest_free_tile(knowledge)
            action = navigation.next_step(knowledge, position)

        return action, "defending"
