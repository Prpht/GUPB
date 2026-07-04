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
    def emergency_move(
        self,
        world: WorldState,
        pressure_tiles: set[coordinates.Coords],
    ) -> characters.Action | None:
        current_risk = self._risk(world, world.position, pressure_tiles)
        current_in_hazard = (
            world.position in world.fire_tiles
            or world.position in world.mist_tiles
            or world.predicted_mist(world.position, 1)
            or (world.health <= 3 and world.position in pressure_tiles)
        )
        if not current_in_hazard:
            return None

        best_step: coordinates.Coords | None = None
        best_score = current_risk
        for direction in DIRS:
            candidate = world.position + direction
            if not world.passable(candidate):
                continue
            score = self._risk(world, candidate, pressure_tiles)
            if world.menhir_position is not None and world.nearest_mist_distance() is not None:
                score += 0.2 * (
                    abs(candidate.x - world.menhir_position.x)
                    + abs(candidate.y - world.menhir_position.y)
                )
            if score < best_score:
                best_score = score
                best_step = candidate

        if best_step is None:
            return None
        return self.move_action(world, best_step)

    def exploratory_move(
        self,
        world: WorldState,
        pressure_tiles: set[coordinates.Coords],
    ) -> characters.Action | None:
        best_step: coordinates.Coords | None = None
        best_score = 1e18
        for direction in DIRS:
            candidate = world.position + direction
            if not world.passable(candidate):
                continue
            score = self._risk(world, candidate, pressure_tiles)
            if candidate in world.recent_positions:
                score += 2.5
            unknown_neighbors = sum(1 for neighbor in DIRS if candidate + neighbor not in world.known_terrain)
            score -= 0.35 * unknown_neighbors
            if world.menhir_position is not None and world.nearest_mist_distance() is not None:
                score += 0.08 * (
                    abs(candidate.x - world.menhir_position.x)
                    + abs(candidate.y - world.menhir_position.y)
                )
            if score < best_score:
                best_score = score
                best_step = candidate

        if best_step is None:
            return None
        return self.move_action(world, best_step)

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
            risk += 80
        if coords in world.mist_tiles:
            risk += 55
        elif world.predicted_mist(coords, 1):
            risk += 30
        if coords in pressure_tiles:
            risk += 12 if world.health <= 4 else 7
        recent = set(world.recent_positions)
        if coords in recent:
            risk += 0.8
        near_walls = 0
        for d in DIRS:
            terrain = world.known_terrain.get(coords + d)
            if terrain in {"wall", "sea"}:
                near_walls += 1
        if near_walls >= 3:
            risk += 2.0
        return risk
