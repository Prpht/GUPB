from typing import Optional
import random

import numpy as np

from gupb.model.characters import Action, Facing
from gupb.model.coordinates import Coords, sub_coords, add_coords

from gupb.controller.batman.heuristic.navigation import Navigation
from gupb.controller.batman.heuristic.passthrough import Passthrough
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


class HidingStrategy:
    def __init__(
        self,
        passthrough: Passthrough,
        hideouts_count: int = 21,
        safe_hampions_alive_count: int = 5,
    ):
        self._passthrough = passthrough
        self._navigation = passthrough.navigation
        self._arena_size = passthrough.arena_size
        self._hideouts_count = hideouts_count
        self._hideouts = self._detect_hideouts()
        self._current_objective = None
        self._vulnerable_directions = dict()
        self._safe_hampions_alive_count = safe_hampions_alive_count

        self._last_position_moving_backwards = None

    def _detect_hideouts(self) -> list[Coords]:
        potential_hideouts = []
        for x, y in np.ndindex(self._arena_size):
            coords = Coords(x, y)
            if self._navigation.is_passable_tile(
                coords
            ) and self._navigation.is_corner_tile(coords):
                potential_hideouts.append(coords)

        if len(potential_hideouts) < self._hideouts_count:
            potential_hideouts = []
            for x, y in np.ndindex(self._arena_size):
                coords = Coords(x, y)
                if self._navigation.is_passable_tile(coords):
                    potential_hideouts.append(coords)

        delta1 = Coords(1, 1)
        delta2 = Coords(2, 2)
        hideout2danger = dict()
        for hideout in potential_hideouts:
            hideout2danger[hideout] = self._passthrough[hideout]
            for neigh in self._navigation.iterate_tiles_in_region_boundary(
                sub_coords(hideout, delta1), add_coords(hideout, delta1)
            ):
                if self._navigation.is_passable_tile(neigh):
                    hideout2danger[hideout] += 0.5 * self._passthrough[neigh]
            for neigh2 in self._navigation.iterate_tiles_in_region_boundary(
                sub_coords(hideout, delta2), add_coords(hideout, delta2)
            ):
                if self._navigation.is_passable_tile(neigh2):
                    hideout2danger[hideout] += 0.15 * self._passthrough[neigh2]

        return sorted(hideout2danger, key=hideout2danger.get)[: self._hideouts_count]

    def decide(
        self, knowledge: Knowledge, events: list[Event], navigation: Navigation
    ) -> tuple[Optional[Action], str]:
        # if knowledge.arena.menhir_position is None:
        #     return None, "scouting"

        # hide until we see mist close enough (10 tiles?) or the number of alive enemies has dropped to less than 5?
        if (
            knowledge.champions_alive <= self._safe_hampions_alive_count
            or knowledge.mist_distance <= 10
        ):
            return None, "rotating"

        for event in events:
            match event:
                case EnemyFoundEvent(enemy) if enemy.position in weapon_cut_positions(
                    knowledge.champion, knowledge
                ):
                    return None, "fighting"
                # case ConsumableFoundEvent(consumable) \
                #         if navigation.manhattan_terrain_distance(consumable.position, knowledge.position) <= 2:
                #     return None, "scouting"
                case IdlePenaltyEvent(episodes_to_penalty) if episodes_to_penalty <= 2:
                    return (
                        random.choice([Action.TURN_LEFT, Action.TURN_RIGHT]),
                        "hiding",
                    )

        if self._current_objective is None and knowledge.position not in self._hideouts:
            related_position = (
                knowledge.arena.menhir_position
                if knowledge.arena.menhir_position
                else knowledge.position
            )
            self._current_objective = min(
                self._hideouts,
                key=lambda hideout: navigation.manhattan_terrain_distance(
                    hideout, related_position
                ),
            )

        if knowledge.position == self._current_objective:
            self._current_objective = None

        if self._current_objective is not None:
            best_objective = min(
                self._hideouts,
                key=lambda hideout: navigation.manhattan_terrain_distance(
                    hideout, knowledge.position
                ),
            )

            if best_objective != self._current_objective:
                self._current_objective = best_objective

            self._vulnerable_directions = dict()
            action = self._navigation.next_fastest_step(knowledge, self._current_objective)

            # if action == Action.STEP_BACKWARD:
            #     if self._last_position_moving_backwards is not None \
            #             and self._last_position_moving_backwards == knowledge.position:
            #         return navigation.next_step(knowledge, self._current_objective), "hiding"
            #     else:
            #         self._last_position_moving_backwards = knowledge.position
            # else:
            #     self._last_position_moving_backwards = None

            if action == Action.STEP_LEFT:
                left_tile_coords = navigation.left_tile(knowledge.position, knowledge.champion.facing)
                if knowledge.visible_tiles[left_tile_coords].character is not None:
                    return Action.TURN_LEFT, "hiding"
            elif action == Action.STEP_RIGHT:
                right_tile_coords = navigation.right_tile(knowledge.position, knowledge.champion.facing)
                if knowledge.visible_tiles[right_tile_coords].character is not None:
                    return Action.TURN_RIGHT, "hiding"

            return action, "hiding"

        if knowledge.champion.facing in self._vulnerable_directions:
            self._vulnerable_directions[knowledge.champion.facing] = knowledge.episode

        if not self._vulnerable_directions:
            self._vulnerable_directions = {
                direction: knowledge.episode
                if knowledge.champion.facing == direction
                else 0
                for direction in [Facing.UP, Facing.RIGHT, Facing.DOWN, Facing.LEFT]
                if self._navigation.is_passable_tile(
                    add_coords(knowledge.position, direction.value)
                )
            }

        # FIXME it cannot be empty, but it happened once
        # if we have only one such direction, we will not move, but we will react to the idle penalty
        last_checked_direction = min(
            self._vulnerable_directions, key=self._vulnerable_directions.get
        )
        action = self._navigation.turn(
            knowledge.champion.facing, last_checked_direction
        )
        return action if action is not None else Action.DO_NOTHING, "hiding"
