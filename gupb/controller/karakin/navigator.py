from __future__ import annotations

from dataclasses import dataclass
import heapq
import math

from gupb.model import characters
from gupb.model import coordinates

from .features import StrategicContext
from .strategy import StrategicMode
from .utils import (
    CARDINAL_DIRECTIONS,
    MOVEMENT_ACTIONS,
    effect_types,
    manhattan,
    movement_action_for_direction,
    movement_direction,
)
from .weapon_info import can_hit, is_weapon_upgrade, weapon_base, weapon_rank
from .world_memory import WorldMemory


@dataclass(frozen=True, slots=True)
class NavigationChoice:
    action: characters.Action
    target: coordinates.Coords | None
    reason: str


class Navigator:
    def hazard_escape_action(
        self,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> NavigationChoice | None:
        current_tile = context.knowledge.visible_tiles.get(context.position)
        current_hazards = effect_types(current_tile)
        currently_in_hazard = bool(current_hazards & {"mist", "fire"})

        best_action: characters.Action | None = None
        best_score = -math.inf
        for action in MOVEMENT_ACTIONS:
            direction = movement_direction(action, context.facing)
            if direction is None:
                continue
            candidate = context.position + direction
            if not memory.is_known_passable(candidate):
                continue
            tile = context.knowledge.visible_tiles.get(candidate)
            if tile is not None and tile.character is not None:
                continue

            hazards = self._known_hazards(candidate, context, memory)
            score = 0.0
            if currently_in_hazard and not hazards:
                score += 80.0
            if "fire" in hazards:
                score -= 140.0
            if "mist" in hazards:
                score -= 70.0 if context.health > 3 else 140.0

            if context.mist_positions:
                nearest_mist = min(manhattan(candidate, mist) for mist in context.mist_positions)
                current_nearest_mist = min(manhattan(context.position, mist) for mist in context.mist_positions)
                score += 12.0 * float(nearest_mist - current_nearest_mist)

            if memory.menhir_position is not None:
                current_menhir_distance = manhattan(context.position, memory.menhir_position)
                candidate_menhir_distance = manhattan(candidate, memory.menhir_position)
                score += 4.0 * float(current_menhir_distance - candidate_menhir_distance)

            if self._enemy_threatens(candidate, context, memory):
                score -= 28.0
            if candidate in memory.recent_positions:
                score -= 4.0

            if score > best_score:
                best_score = score
                best_action = action

        if best_action is None:
            return None
        return NavigationChoice(best_action, None, "hazard_escape")

    def action_for_mode(
        self,
        mode: StrategicMode,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> NavigationChoice:
        targets = self._targets_for_mode(mode, context, memory)
        if targets:
            action = self._path_action(context, memory, targets)
            if action is not None:
                return NavigationChoice(action, self._nearest_target(context.position, targets), mode.name.lower())

        if mode not in (StrategicMode.EXPLORE, StrategicMode.RETREAT):
            fallback_targets = memory.frontier_targets()
            if fallback_targets:
                action = self._path_action(context, memory, fallback_targets)
                if action is not None:
                    return NavigationChoice(
                        action,
                        self._nearest_target(context.position, fallback_targets),
                        "fallback_explore",
                    )

        if mode == StrategicMode.RETREAT and context.visible_enemies:
            action = self._retreat_action(context, memory)
            if action is not None:
                return NavigationChoice(action, None, "retreat")

        scan_action = self._scan_action(context)
        return NavigationChoice(scan_action, None, "scan")

    def _targets_for_mode(
        self,
        mode: StrategicMode,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> set[coordinates.Coords]:
        if mode == StrategicMode.GO_MENHIR:
            return self._menhir_targets(context, memory)
        if mode == StrategicMode.HEAL:
            return set(memory.known_consumables.keys())
        if mode == StrategicMode.LOOT_WEAPON:
            return {
                coords_
                for coords_, weapon_name in memory.known_loot.items()
                if is_weapon_upgrade(context.weapon_name, weapon_name)
            }
        if mode == StrategicMode.RETREAT:
            return self._safe_retreat_targets(context, memory)
        if mode == StrategicMode.FIGHT:
            return self._combat_targets(context, memory)
        return memory.frontier_targets()

    def _combat_targets(
        self,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> set[coordinates.Coords]:
        if not context.visible_enemies:
            return set()

        enemy_position, _ = context.visible_enemies[0]
        target_weapon = "bow_loaded" if weapon_base(context.weapon_name) == "bow" else context.weapon_name
        targets: set[coordinates.Coords] = set()
        for coords_ in memory.known_tile_type:
            if manhattan(coords_, enemy_position) > 8:
                continue
            if not self._usable_target(coords_, context, memory):
                continue
            if any(
                can_hit(
                    target_weapon,
                    coords_,
                    facing,
                    enemy_position,
                    memory.tile_type_at,
                    lambda c: memory.character_at(c, context.knowledge),
                )
                for facing in characters.Facing
            ):
                targets.add(coords_)

        if targets:
            return targets

        for delta in CARDINAL_DIRECTIONS:
            candidate = enemy_position + delta
            if self._usable_target(candidate, context, memory):
                targets.add(candidate)
        return targets

    @staticmethod
    def _usable_target(
        coords_: coordinates.Coords,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> bool:
        if not memory.is_known_passable(coords_):
            return False
        tile = context.knowledge.visible_tiles.get(coords_)
        return tile is None or tile.character is None or coords_ == context.position

    def _menhir_targets(
        self,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> set[coordinates.Coords]:
        if memory.menhir_position is None:
            return set()

        menhir = memory.menhir_position
        if context.mist_positions or context.knowledge.no_of_champions_alive <= 3:
            radius = 1
        else:
            radius = 2

        targets: set[coordinates.Coords] = set()
        for coords_, tile_type in memory.known_tile_type.items():
            if not memory.is_known_passable(coords_):
                continue
            if manhattan(coords_, menhir) <= radius:
                targets.add(coords_)
        targets.add(menhir)
        return targets

    def _safe_retreat_targets(
        self,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> set[coordinates.Coords]:
        if not context.visible_enemies:
            return memory.frontier_targets()

        nearest_enemy_position, _ = context.visible_enemies[0]
        candidates: list[tuple[float, coordinates.Coords]] = []
        for coords_, tile_type in memory.known_tile_type.items():
            if not memory.is_known_passable(coords_):
                continue
            if manhattan(context.position, coords_) > 8:
                continue
            tile = context.knowledge.visible_tiles.get(coords_)
            if tile is not None and tile.character is not None and coords_ != context.position:
                continue
            score = float(manhattan(coords_, nearest_enemy_position))
            if tile is not None:
                names = effect_types(tile)
                if "mist" in names:
                    score -= 12.0
                if "fire" in names:
                    score -= 18.0
            if memory.menhir_position is not None:
                score -= 0.25 * manhattan(coords_, memory.menhir_position)
            candidates.append((score, coords_))

        candidates.sort(reverse=True, key=lambda item: item[0])
        return {coords_ for _, coords_ in candidates[:8]}

    def _path_action(
        self,
        context: StrategicContext,
        memory: WorldMemory,
        targets: set[coordinates.Coords],
    ) -> characters.Action | None:
        if context.position in targets:
            return None

        blocked = {
            coords_
            for coords_, tile in context.knowledge.visible_tiles.items()
            if tile.character is not None and coords_ != context.position
        }
        distances, previous = self._dijkstra(context, memory, targets, blocked)
        if context.position not in previous and context.position not in targets:
            return None

        first_step = self._first_step_from_previous(context.position, targets, previous)
        if first_step is None:
            return None
        direction = first_step - context.position
        action = movement_action_for_direction(direction, context.facing)
        if action is not None:
            return action

        desired_facing = self._desired_facing(context.position, first_step)
        if desired_facing is None or desired_facing == context.facing:
            return None
        if desired_facing == context.facing.turn_left():
            return characters.Action.TURN_LEFT
        if desired_facing == context.facing.turn_right():
            return characters.Action.TURN_RIGHT
        return characters.Action.TURN_RIGHT

    def _dijkstra(
        self,
        context: StrategicContext,
        memory: WorldMemory,
        targets: set[coordinates.Coords],
        blocked: set[coordinates.Coords],
    ) -> tuple[dict[coordinates.Coords, float], dict[coordinates.Coords, coordinates.Coords | None]]:
        start = context.position
        distances: dict[coordinates.Coords, float] = {start: 0.0}
        previous: dict[coordinates.Coords, coordinates.Coords | None] = {start: None}
        heap: list[tuple[float, int, coordinates.Coords]] = [(0.0, 0, start)]
        counter = 0

        while heap:
            cost, _, coords_ = heapq.heappop(heap)
            if coords_ in targets and coords_ != start:
                break
            if cost > distances.get(coords_, math.inf):
                continue
            for delta in CARDINAL_DIRECTIONS:
                neighbor = coords_ + delta
                if neighbor in blocked or not memory.is_known_passable(neighbor):
                    continue
                step_cost = self._step_cost(neighbor, context, memory)
                new_cost = cost + step_cost
                if new_cost < distances.get(neighbor, math.inf):
                    distances[neighbor] = new_cost
                    previous[neighbor] = coords_
                    counter += 1
                    heapq.heappush(heap, (new_cost, counter, neighbor))
        return distances, previous

    def _step_cost(
        self,
        coords_: coordinates.Coords,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> float:
        cost = 1.0
        tile = context.knowledge.visible_tiles.get(coords_)
        if tile is not None:
            names = effect_types(tile)
            if "mist" in names:
                cost += 45.0 if context.health > 3 else 90.0
            if "fire" in names:
                cost += 70.0
        else:
            if coords_ in memory.known_mist_positions:
                cost += 45.0 if context.health > 3 else 90.0
            if coords_ in memory.known_fire_positions:
                cost += 70.0
        if coords_ in memory.recent_positions:
            cost += 2.0
        if self._enemy_threatens(coords_, context, memory):
            cost += 24.0
        if memory.menhir_position is not None and context.mist_positions:
            cost += 0.15 * manhattan(coords_, memory.menhir_position)
        return cost

    def _enemy_threatens(
        self,
        coords_: coordinates.Coords,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> bool:
        for enemy_position, enemy in context.visible_enemies[:3]:
            if can_hit(
                enemy.weapon.name,
                enemy_position,
                enemy.facing,
                coords_,
                memory.tile_type_at,
                lambda c: memory.character_at(c, context.knowledge),
            ):
                return True
            if manhattan(coords_, enemy_position) == 1 and weapon_rank(enemy.weapon.name) >= weapon_rank(context.weapon_name):
                return True
        return False

    def _first_step_from_previous(
        self,
        start: coordinates.Coords,
        targets: set[coordinates.Coords],
        previous: dict[coordinates.Coords, coordinates.Coords | None],
    ) -> coordinates.Coords | None:
        reachable_targets = [target for target in targets if target in previous]
        if not reachable_targets:
            return None
        target = min(reachable_targets, key=lambda coords_: self._previous_depth(coords_, previous))
        current = target
        while previous.get(current) is not None and previous[current] != start:
            current = previous[current]
        if previous.get(current) == start:
            return current
        return None

    @staticmethod
    def _previous_depth(
        coords_: coordinates.Coords,
        previous: dict[coordinates.Coords, coordinates.Coords | None],
    ) -> int:
        depth = 0
        current = coords_
        while previous.get(current) is not None:
            depth += 1
            current = previous[current]
        return depth

    def _retreat_action(
        self,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> characters.Action | None:
        if not context.visible_enemies:
            return None
        enemy_position, _ = context.visible_enemies[0]
        best_action: characters.Action | None = None
        best_score = -math.inf
        for action in MOVEMENT_ACTIONS:
            direction = movement_direction(action, context.facing)
            if direction is None:
                continue
            candidate = context.position + direction
            if not memory.is_known_passable(candidate):
                continue
            tile = context.knowledge.visible_tiles.get(candidate)
            if tile is not None and tile.character is not None:
                continue
            score = float(manhattan(candidate, enemy_position))
            if self._enemy_threatens(candidate, context, memory):
                score -= 5.0
            if tile is not None:
                names = effect_types(tile)
                if "mist" in names:
                    score -= 6.0
                if "fire" in names:
                    score -= 10.0
            else:
                if candidate in memory.known_mist_positions:
                    score -= 6.0
                if candidate in memory.known_fire_positions:
                    score -= 10.0
            if score > best_score:
                best_score = score
                best_action = action
        return best_action

    @staticmethod
    def _known_hazards(
        coords_: coordinates.Coords,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> set[str]:
        tile = context.knowledge.visible_tiles.get(coords_)
        hazards = effect_types(tile)
        if coords_ in memory.known_mist_positions:
            hazards.add("mist")
        if coords_ in memory.known_fire_positions:
            hazards.add("fire")
        return hazards

    @staticmethod
    def _scan_action(context: StrategicContext) -> characters.Action:
        if context.knowledge.no_of_champions_alive <= 2 and context.mist_positions:
            return characters.Action.DO_NOTHING
        return characters.Action.TURN_LEFT if context.knowledge.position.x % 2 == 0 else characters.Action.TURN_RIGHT

    @staticmethod
    def _nearest_target(
        position: coordinates.Coords,
        targets: set[coordinates.Coords],
    ) -> coordinates.Coords | None:
        if not targets:
            return None
        return min(targets, key=lambda target: manhattan(position, target))

    @staticmethod
    def _desired_facing(
        origin: coordinates.Coords,
        target: coordinates.Coords,
    ) -> characters.Facing | None:
        delta = target - origin
        for facing in characters.Facing:
            if facing.value == delta:
                return facing
        return None
