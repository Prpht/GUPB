from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Iterable

from gupb.model import characters, coordinates

from .worldstate import WorldState

DIRS = [
    coordinates.Coords(1, 0),
    coordinates.Coords(-1, 0),
    coordinates.Coords(0, 1),
    coordinates.Coords(0, -1),
]


@dataclass
class PathChoice:
    target: coordinates.Coords
    next_step: coordinates.Coords
    total_cost: float


class Navigator:
    def pick_route(
        self,
        world: WorldState,
        targets: Iterable[tuple[coordinates.Coords, float]],
        pressure_tiles: set[coordinates.Coords],
    ) -> PathChoice | None:
        goal_bonus = {coord: bonus for coord, bonus in targets}
        if not goal_bonus:
            return None

        start = world.position
        frontier: list[tuple[float, coordinates.Coords]] = [(0.0, start)]
        came_from: dict[coordinates.Coords, coordinates.Coords] = {}
        best: dict[coordinates.Coords, float] = {start: 0.0}
        best_goal: tuple[coordinates.Coords, float] | None = None

        while frontier:
            current_score, current = heapq.heappop(frontier)
            if current_score > best.get(current, 1e18):
                continue

            if current in goal_bonus:
                final_score = current_score - goal_bonus[current]
                if best_goal is None or final_score < best_goal[1]:
                    best_goal = (current, final_score)

            for direction in DIRS:
                nxt = current + direction
                if not world.passable(nxt):
                    continue
                step_cost = 1.0 + self._risk(world, nxt, pressure_tiles)
                candidate = current_score + step_cost
                if candidate < best.get(nxt, 1e18):
                    best[nxt] = candidate
                    came_from[nxt] = current
                    heapq.heappush(frontier, (candidate, nxt))

        if best_goal is None:
            return None

        goal = best_goal[0]
        cursor = goal
        while came_from.get(cursor) and came_from[cursor] != start:
            cursor = came_from[cursor]
        next_step = cursor if came_from.get(cursor) == start else goal
        return PathChoice(target=goal, next_step=next_step, total_cost=best_goal[1])

    def move_action(self, world: WorldState, next_step: coordinates.Coords) -> characters.Action:
        delta = next_step - world.position
        facing = world.facing
        options = {
            facing.value: characters.Action.STEP_FORWARD,
            facing.opposite().value: characters.Action.STEP_BACKWARD,
            facing.turn_left().value: characters.Action.STEP_LEFT,
            facing.turn_right().value: characters.Action.STEP_RIGHT,
        }
        return options.get(delta, characters.Action.TURN_RIGHT)

    def _risk(self, world: WorldState, coords: coordinates.Coords, pressure_tiles: set[coordinates.Coords]) -> float:
        risk = 0.0
        if coords in world.fire_tiles:
            risk += 50
        if coords in world.mist_tiles:
            risk += 25
        if coords in pressure_tiles:
            risk += 6
        if coords in set(world.recent_positions):
            risk += 0.8
        near_walls = 0
        for d in DIRS:
            terrain = world.known_terrain.get(coords + d)
            if terrain in {"wall", "sea"}:
                near_walls += 1
        if near_walls >= 3:
            risk += 2.0
        return risk
