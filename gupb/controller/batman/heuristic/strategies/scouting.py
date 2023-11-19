from typing import Optional

from gupb.model.coordinates import Coords
from gupb.model.characters import Action

from gupb.controller.batman.heuristic.navigation import Navigation
from gupb.controller.batman.heuristic.strategies.utils import weapon_cut_positions
from gupb.controller.batman.heuristic.events import (
    Event,
    MenhirFoundEvent,
    WeaponFoundEvent,
    WeaponPickedUpEvent,
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


class ScoutingStrategy:
    def __init__(self):
        self._current_objective = None
        self._current_objective_name = None

    def decide(
        self, knowledge: Knowledge, events: list[Event], navigation: Navigation
    ) -> tuple[Optional[Action], str]:
        if knowledge.position == self._current_objective:
            self._current_objective = None
            self._current_objective_name = None

        in_enemy_cut_position = False
        for event in events:
            match event:
                # case MenhirFoundEvent(_):
                #     self._current_objective = None
                #     self._current_objective_name = None
                case ConsumableFoundEvent(consumable):
                    self._current_objective = consumable.position
                    self._current_objective_name = consumable.name
                case WeaponFoundEvent(weapon) if (
                    knowledge.champion.weapon == "knife"
                    and self._current_objective_name != "axe"
                ) or (weapon.name == "axe" and knowledge.champion.weapon != "axe"):
                    self._current_objective = weapon.position
                    self._current_objective_name = weapon.name
                case EnemyFoundEvent(enemy) if enemy.position in weapon_cut_positions(
                    knowledge.champion, knowledge
                ):
                    return None, "fighting"
                case EnemyFoundEvent(
                    enemy
                ) if knowledge.position in weapon_cut_positions(enemy, knowledge):
                    in_enemy_cut_position = True

            # if isinstance(event, LosingHealthEvent):  # TODO this should give us a hint about the enemy position
            #     if knowledge.champion.health <= 5:
            #         # TODO better to turn to the side, which is not occupied by the wall or sea
            #         return Action.ATTACK, "defending"

        # if mist is too close, we should rotate to the menhir
        if knowledge.mist_distance <= 7 and knowledge.arena.menhir_position:
            return None, "rotating"

        # if we are not doing anything, we should hide
        if (
            self._current_objective is None
            and knowledge.arena.menhir_position
            # and knowledge.champion.weapon != "knife"
        ):
            return None, "hiding"

        # if no objective is set, we should scout the map
        # currently we are looking for the furthest tile from the champion, and we are going there
        # TODO change this one
        if self._current_objective is None:
            champion_position = knowledge.champion.position
            max_distance = 0
            for position, tile in knowledge.arena.explored_map.items():
                if not tile.passable:
                    continue

                distance = navigation.manhattan_distance(champion_position, position)
                if distance > max_distance:
                    max_distance = distance
                    self._current_objective = position
                    self._current_objective_name = "scouting"

            # if we look straight at the wall, we should turn right
            if max_distance == 0:
                return Action.TURN_RIGHT, "scouting"

        action = navigation.next_step(knowledge, self._current_objective)

        # this means we want to go through tile occupied by someone having an amulet,
        # or something we cannot attack him with, so we run away
        if action == Action.STEP_FORWARD and in_enemy_cut_position:
            front_tile = navigation.front_tile(
                knowledge.position, knowledge.champion.facing
            )
            champions_positions = [
                champion.position for champion in knowledge.last_seen_champions.values()
            ]
            if front_tile in champions_positions:
                return None, "running_away"

        return action, "scouting"
