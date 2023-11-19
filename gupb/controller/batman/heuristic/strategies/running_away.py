from typing import Optional

from gupb.model.characters import Action
from gupb.model.coordinates import Coords

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


class RunningAwayStrategy:
    def __init__(self):
        self._map_grid = None
        self._current_objective = None
        self._recursion_depth = 0
        self._last_episode = None

    def decide(
        self, knowledge: Knowledge, events: list[Event], navigation: Navigation
    ) -> tuple[Optional[Action], str]:
        if knowledge.position == self._current_objective:
            self._map_grid = None
            self._current_objective = None
            return None, "hiding"

        if self._current_objective is None:
            grid = navigation.base_grid()
            for champion in knowledge.last_seen_champions.values():
                pos = champion.position

                # TODO is x, y order correct?
                # champion himself
                grid[pos.y, pos.x] = 0

                # champion's neighboring tiles
                for neigh_pos in [
                    (pos.y - 1, pos.x),
                    (pos.y + 1, pos.x),
                    (pos.y, pos.x - 1),
                    (pos.y, pos.x + 1),
                ]:
                    if not navigation.is_passable_tile(
                        Coords(neigh_pos[1], neigh_pos[0])
                    ):
                        continue

                    grid[neigh_pos] = 3 + grid[neigh_pos] if grid[neigh_pos] != 0 else 0

                # champion's field of attack
                for cut_pos in weapon_cut_positions(champion, knowledge):
                    if not navigation.is_passable_tile(cut_pos):
                        continue

                    cut_pos_tuple = (cut_pos.y, cut_pos.x)
                    grid[cut_pos_tuple] = (
                        9 + grid[cut_pos_tuple] if grid[cut_pos_tuple] != 0 else 0
                    )

            self._map_grid = grid
            self._current_objective = navigation.find_nearest_safe_tile(
                knowledge, self._map_grid
            )

        action = navigation.next_fastest_step(knowledge, self._current_objective)

        # if there is a champion in front of us, and we need to step forward
        # we reset the grid and the objective, and try to run away again
        if action == Action.STEP_FORWARD:
            front_tile = navigation.front_tile(
                knowledge.position, knowledge.champion.facing
            )
            champions_positions = [
                champion.position for champion in knowledge.last_seen_champions.values()
            ]
            if front_tile in champions_positions:
                # guard against infinite recursion
                if self._last_episode == knowledge.episode:
                    self._recursion_depth += 1
                else:
                    self._last_episode = knowledge.episode
                    self._recursion_depth = 0

                if self._recursion_depth > 3:
                    position = navigation.find_closest_free_tile(knowledge)
                    action = navigation.next_fastest_step(knowledge, position)
                    return action, "hiding"

                self._map_grid = None
                self._current_objective = None
                return None, "running_away"

        return action, "running_away"
