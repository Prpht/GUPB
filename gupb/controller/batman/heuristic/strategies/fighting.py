from typing import Optional

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
)

from gupb.controller.batman.knowledge.knowledge import (
    Knowledge,
    ArenaKnowledge,
    TileKnowledge,
    ChampionKnowledge,
    WeaponKnowledge,
    ConsumableKnowledge,
)


class FightingStrategy:
    def __init__(self):
        pass

    def decide(
        self, knowledge: Knowledge, events: list[Event], navigation: Navigation
    ) -> tuple[Optional[Action], str]:
        for event in events:
            match event:
                case EnemyFoundEvent(enemy) if enemy.position in weapon_cut_positions(
                    knowledge.champion, knowledge
                ):
                    # currently all the weapons deal the same damage
                    # TODO is there a smarter decision, than simply health difference?
                    # TODO we could try to attack those reaching better scores overall to eliminate them
                    if (
                        knowledge.champion.position
                        in weapon_cut_positions(enemy, knowledge)
                        and enemy.health > knowledge.champion.health
                    ):
                        return None, "running_away"
                    else:
                        return Action.ATTACK, "fighting"
                case EnemyFoundEvent(
                    enemy
                ) if knowledge.champion.position in weapon_cut_positions(
                    enemy, knowledge
                ):
                    # TODO calculate if moving to kill him is more profitable than escaping
                    # moves_to_be_able_to_attack = ...
                    # if enemy.health < me.health - moves_to_be_able_to_attack * damage:
                    #     then fight
                    return None, "running_away"

        return None, "hiding"
