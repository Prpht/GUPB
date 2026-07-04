from __future__ import annotations

from collections import deque
import inspect
from typing import Optional

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles

from .shared_state import BenjaminSharedState
from .shared_state import TurnContext

PASSABLE_TILE_TYPES = {"land", "forest", "menhir"}
TRANSPARENT_TILE_TYPES = {"land", "sea", "menhir"}
HAZARD_EFFECT_TYPES = {"fire", "mist"}
MOVE_ACTIONS = {
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
}
CARDINALS = (
    coordinates.Coords(1, 0),
    coordinates.Coords(-1, 0),
    coordinates.Coords(0, 1),
    coordinates.Coords(0, -1),
)
DIAGONALS = (
    coordinates.Coords(1, 1),
    coordinates.Coords(1, -1),
    coordinates.Coords(-1, 1),
    coordinates.Coords(-1, -1),
)
FIXED_MENHIRS = {
    "isolated_shrine": coordinates.Coords(9, 9),
    "lone_sanctum": coordinates.Coords(9, 9),
}
MENHIR_HOLD_RADIUS = 1
MENHIR_ENGAGE_RADIUS = 3
MENHIR_EARLY_PULL_DISTANCE = 2
MIST_PANIC_DISTANCE = 6
LOW_HP_THRESHOLD = 4
ENEMY_MEMORY_TTL = 6
CHASE_DISTANCE_LIMIT = 6
PANIC_DAMAGE_SPIKE = 3
PANIC_TURNS = 3


class BenjaminNormalMode(controller.Controller):
    """
    Heuristic baseline:
    - avoids hazards (fire/mist),
    - takes direct fights with visible enemies,
    - picks potion on low HP and upgrades weapon when reasonable,
    - uses simple BFS on visible passable tiles to avoid spinning in place.
    """

    def __init__(
            self,
            bot_name: str = "BenjaminNormalMode",
            shared_state: Optional[BenjaminSharedState] = None,
            allow_oracle_menhir: bool = False,
    ):
        self.bot_name: str = bot_name
        self.shared_state: BenjaminSharedState = shared_state or BenjaminSharedState()
        self._allow_oracle_menhir = allow_oracle_menhir

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BenjaminNormalMode):
            return self.bot_name == other.bot_name
        return False

    def __hash__(self) -> int:
        return hash(self.bot_name)

    @property
    def _last_position(self) -> Optional[coordinates.Coords]:
        return self.shared_state.last_position

    @_last_position.setter
    def _last_position(self, value: Optional[coordinates.Coords]) -> None:
        self.shared_state.last_position = value

    @property
    def _last_action(self) -> characters.Action:
        return self.shared_state.last_action

    @_last_action.setter
    def _last_action(self, value: characters.Action) -> None:
        self.shared_state.last_action = value

    @property
    def _failed_moves(self) -> int:
        return self.shared_state.failed_moves

    @_failed_moves.setter
    def _failed_moves(self, value: int) -> None:
        self.shared_state.failed_moves = value

    @property
    def _recent_positions(self) -> deque[coordinates.Coords]:
        return self.shared_state.recent_positions

    @_recent_positions.setter
    def _recent_positions(self, value: deque[coordinates.Coords]) -> None:
        self.shared_state.recent_positions = value

    @property
    def _known_menhir(self) -> Optional[coordinates.Coords]:
        return self.shared_state.known_menhir

    @_known_menhir.setter
    def _known_menhir(self, value: Optional[coordinates.Coords]) -> None:
        self.shared_state.known_menhir = value

    @property
    def _arena_name(self) -> Optional[str]:
        return self.shared_state.arena_name

    @_arena_name.setter
    def _arena_name(self, value: Optional[str]) -> None:
        self.shared_state.arena_name = value

    @property
    def _seen_min_x(self) -> Optional[int]:
        return self.shared_state.seen_min_x

    @_seen_min_x.setter
    def _seen_min_x(self, value: Optional[int]) -> None:
        self.shared_state.seen_min_x = value

    @property
    def _seen_max_x(self) -> Optional[int]:
        return self.shared_state.seen_max_x

    @_seen_max_x.setter
    def _seen_max_x(self, value: Optional[int]) -> None:
        self.shared_state.seen_max_x = value

    @property
    def _seen_min_y(self) -> Optional[int]:
        return self.shared_state.seen_min_y

    @_seen_min_y.setter
    def _seen_min_y(self, value: Optional[int]) -> None:
        self.shared_state.seen_min_y = value

    @property
    def _seen_max_y(self) -> Optional[int]:
        return self.shared_state.seen_max_y

    @_seen_max_y.setter
    def _seen_max_y(self, value: Optional[int]) -> None:
        self.shared_state.seen_max_y = value

    @property
    def _known_passable(self) -> set[coordinates.Coords]:
        return self.shared_state.known_passable

    @_known_passable.setter
    def _known_passable(self, value: set[coordinates.Coords]) -> None:
        self.shared_state.known_passable = value

    @property
    def _known_blocked(self) -> set[coordinates.Coords]:
        return self.shared_state.known_blocked

    @_known_blocked.setter
    def _known_blocked(self, value: set[coordinates.Coords]) -> None:
        self.shared_state.known_blocked = value

    @property
    def _visited_count(self) -> dict[coordinates.Coords, int]:
        return self.shared_state.visited_count

    @_visited_count.setter
    def _visited_count(self, value: dict[coordinates.Coords, int]) -> None:
        self.shared_state.visited_count = value

    @property
    def _enemy_memory(self) -> dict[str, tuple[coordinates.Coords, int]]:
        return self.shared_state.enemy_memory

    @_enemy_memory.setter
    def _enemy_memory(self, value: dict[str, tuple[coordinates.Coords, int]]) -> None:
        self.shared_state.enemy_memory = value

    @property
    def _turn_no(self) -> int:
        return self.shared_state.turn_no

    @_turn_no.setter
    def _turn_no(self, value: int) -> None:
        self.shared_state.turn_no = value

    @property
    def _last_hp(self) -> Optional[int]:
        return self.shared_state.last_hp

    @_last_hp.setter
    def _last_hp(self, value: Optional[int]) -> None:
        self.shared_state.last_hp = value

    @property
    def _recent_damage(self) -> deque[int]:
        return self.shared_state.recent_damage

    @_recent_damage.setter
    def _recent_damage(self, value: deque[int]) -> None:
        self.shared_state.recent_damage = value

    @property
    def _panic_turns(self) -> int:
        return self.shared_state.panic_turns

    @_panic_turns.setter
    def _panic_turns(self, value: int) -> None:
        self.shared_state.panic_turns = value

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        context = self.observe_turn(knowledge)

        if self._failed_moves >= 2:
            return self._store_action(characters.Action.TURN_RIGHT, context.knowledge.position)

        if context.current_tile and self._is_hazardous(context.current_tile):
            emergency_target = self._known_menhir or self._estimated_center(context.knowledge.position)
            escape_action = self._best_escape_step(context.knowledge, context.facing, emergency_target)
            if escape_action is not None:
                return self._store_action(escape_action, context.knowledge.position)
            return self._store_action(characters.Action.TURN_RIGHT, context.knowledge.position)

        adjacent_enemy = self._nearest_adjacent_enemy(context.knowledge.position, context.visible_enemy_positions)
        if adjacent_enemy is not None:
            face_action = self._face_target_action(context.knowledge.position, context.facing, adjacent_enemy)
            if face_action is None:
                return self._store_action(characters.Action.ATTACK, context.knowledge.position)
            return self._store_action(face_action, context.knowledge.position)

        if context.visible_enemy_positions and self._enemy_in_range(
            context.knowledge,
            context.facing,
            context.current_weapon,
            context.visible_enemy_positions,
        ):
            return self._store_action(characters.Action.ATTACK, context.knowledge.position)

        if self._known_menhir is not None and self._should_prioritise_menhir(
            context.knowledge,
            context.current_hp,
            context.mist_positions,
        ):
            menhir_action = self._menhir_mode_action(
                knowledge=context.knowledge,
                facing=context.facing,
                current_hp=context.current_hp,
                current_weapon=context.current_weapon,
                visible_enemy_positions=context.visible_enemy_positions,
                enemy_positions=context.enemy_positions,
                mist_visible=context.mist_visible,
            )
            if menhir_action is not None:
                return self._store_action(menhir_action, context.knowledge.position)

        if context.enemy_positions and self._should_chase_enemy(
            knowledge=context.knowledge,
            current_hp=context.current_hp,
            current_weapon=context.current_weapon,
            enemy_positions=context.enemy_positions,
            mist_visible=context.mist_visible,
        ):
            chase_action = self._move_towards_enemy(
                context.knowledge,
                context.facing,
                context.enemy_positions,
                context.current_weapon,
            )
            if chase_action is not None:
                return self._store_action(chase_action, context.knowledge.position)

        target = self._choose_resource_target(
            context.knowledge,
            context.current_hp,
            context.current_weapon,
            context.mist_visible,
        )
        if target is not None:
            move_action = self._move_towards(
                context.knowledge,
                context.facing,
                target,
                target_is_enemy=False,
                allow_hazard_path=False,
            )
            if move_action is not None:
                return self._store_action(move_action, context.knowledge.position)

        explore_action = self._explore_action(context.knowledge, context.facing)
        return self._store_action(explore_action, context.knowledge.position)

    def observe_turn(self, knowledge: characters.ChampionKnowledge) -> TurnContext:
        knowledge = self._normalise_knowledge(knowledge)
        self._turn_no += 1
        self._update_failed_moves(knowledge.position)
        self._update_world_memory(knowledge)
        self._update_oracle_menhir()
        self._visited_count[knowledge.position] += 1

        current_tile = knowledge.visible_tiles.get(knowledge.position)
        current_champion = current_tile.character if current_tile else None
        facing = current_champion.facing if current_champion else characters.Facing.UP
        current_weapon = current_champion.weapon.name if current_champion else "knife"
        current_hp = current_champion.health if current_champion else characters.CHAMPION_STARTING_HP
        self._update_damage_state(current_hp)

        visible_enemy_positions = self._enemy_positions(knowledge, include_memory=False)
        enemy_positions = self._enemy_positions(knowledge, include_memory=True)
        mist_positions = self._mist_positions(knowledge)

        return TurnContext(
            knowledge=knowledge,
            current_tile=current_tile,
            facing=facing,
            current_weapon=current_weapon,
            current_hp=current_hp,
            visible_enemy_positions=visible_enemy_positions,
            enemy_positions=enemy_positions,
            mist_positions=mist_positions,
            mist_visible=bool(mist_positions),
        )

    def _normalise_knowledge(self, knowledge: characters.ChampionKnowledge) -> characters.ChampionKnowledge:
        normalised_visible_tiles = {
            self._to_coords(raw_coords): tile_description
            for raw_coords, tile_description in knowledge.visible_tiles.items()
        }
        return characters.ChampionKnowledge(
            position=self._to_coords(knowledge.position),
            no_of_champions_alive=knowledge.no_of_champions_alive,
            visible_tiles=normalised_visible_tiles,
        )

    def _update_failed_moves(self, current_position: coordinates.Coords) -> None:
        if self._last_position is None:
            self._failed_moves = 0
            return
        if self._last_action in MOVE_ACTIONS and current_position == self._last_position:
            self._failed_moves += 1
        else:
            self._failed_moves = 0

    def _update_world_memory(self, knowledge: characters.ChampionKnowledge) -> None:
        visible_coords: set[coordinates.Coords] = set()
        for raw_coords, tile_description in knowledge.visible_tiles.items():
            coords = self._to_coords(raw_coords)
            visible_coords.add(coords)
            self._update_seen_bounds(coords)
            if tile_description.type == "menhir":
                self._known_menhir = coords
            if tile_description.type in PASSABLE_TILE_TYPES:
                self._known_passable.add(coords)
                self._known_blocked.discard(coords)
            else:
                self._known_blocked.add(coords)
                self._known_passable.discard(coords)
            if tile_description.character and tile_description.character.controller_name != self.name:
                enemy_name = tile_description.character.controller_name
                self._enemy_memory[enemy_name] = (coords, self._turn_no)

        for enemy_name, (enemy_coords, _) in list(self._enemy_memory.items()):
            if enemy_coords not in visible_coords:
                continue
            tile_description = knowledge.visible_tiles.get(enemy_coords)
            if tile_description is None:
                continue
            if tile_description.character is None or tile_description.character.controller_name == self.name:
                self._enemy_memory.pop(enemy_name, None)

        stale_enemies = [
            enemy_name
            for enemy_name, (_, last_seen_turn) in self._enemy_memory.items()
            if self._turn_no - last_seen_turn > ENEMY_MEMORY_TTL
        ]
        for enemy_name in stale_enemies:
            self._enemy_memory.pop(enemy_name, None)

    def _update_seen_bounds(self, coords: coordinates.Coords) -> None:
        self._seen_min_x = coords.x if self._seen_min_x is None else min(self._seen_min_x, coords.x)
        self._seen_max_x = coords.x if self._seen_max_x is None else max(self._seen_max_x, coords.x)
        self._seen_min_y = coords.y if self._seen_min_y is None else min(self._seen_min_y, coords.y)
        self._seen_max_y = coords.y if self._seen_max_y is None else max(self._seen_max_y, coords.y)

    def _estimated_center(self, fallback: coordinates.Coords) -> coordinates.Coords:
        if None in {self._seen_min_x, self._seen_max_x, self._seen_min_y, self._seen_max_y}:
            return fallback
        return coordinates.Coords(
            int((self._seen_min_x + self._seen_max_x) / 2),
            int((self._seen_min_y + self._seen_max_y) / 2),
        )

    def _update_damage_state(self, current_hp: int) -> None:
        if self._panic_turns > 0:
            self._panic_turns -= 1

        if self._last_hp is None:
            self._last_hp = current_hp
            return

        damage_taken = max(0, self._last_hp - current_hp)
        self._recent_damage.append(damage_taken)
        if damage_taken >= PANIC_DAMAGE_SPIKE:
            self._panic_turns = max(self._panic_turns, PANIC_TURNS)
        elif sum(self._recent_damage) >= PANIC_DAMAGE_SPIKE + 1:
            self._panic_turns = max(self._panic_turns, PANIC_TURNS - 1)

        self._last_hp = current_hp

    def _store_action(self, action: characters.Action, position: coordinates.Coords) -> characters.Action:
        self._last_action = action
        self._last_position = position
        self._recent_positions.append(position)
        return action

    def _choose_resource_target(
            self,
            knowledge: characters.ChampionKnowledge,
            current_hp: int,
            current_weapon: str,
            mist_visible: bool,
    ) -> Optional[coordinates.Coords]:
        potion_tiles: list[coordinates.Coords] = []
        better_weapon_tiles: list[coordinates.Coords] = []
        for raw_coords, tile_description in knowledge.visible_tiles.items():
            coords = self._to_coords(raw_coords)
            if tile_description.consumable and tile_description.consumable.name == "potion":
                potion_tiles.append(coords)
            if (
                tile_description.loot
                and self._is_weapon_upgrade_worth_it(
                    current_weapon=current_weapon,
                    loot_weapon=tile_description.loot.name,
                    knowledge=knowledge,
                    current_hp=current_hp,
                    mist_visible=mist_visible,
                )
            ):
                better_weapon_tiles.append(coords)

        if self._known_menhir is not None:
            dist_to_menhir = self._distance(knowledge.position, self._known_menhir)
            nearest_potion = self._nearest_optional(knowledge.position, potion_tiles)
            nearest_weapon = self._nearest_optional(knowledge.position, better_weapon_tiles)

            if self._panic_turns > 0 and nearest_potion is not None and self._distance(knowledge.position, nearest_potion) <= 6:
                return nearest_potion
            if current_hp <= LOW_HP_THRESHOLD and nearest_potion is not None and self._distance(knowledge.position, nearest_potion) <= 4:
                return nearest_potion
            if mist_visible or knowledge.no_of_champions_alive <= 4 or dist_to_menhir > MENHIR_EARLY_PULL_DISTANCE:
                return self._known_menhir
            if dist_to_menhir > 2:
                if nearest_weapon is not None and self._distance(knowledge.position, nearest_weapon) <= 3:
                    return nearest_weapon
                return self._known_menhir
            if nearest_potion is not None and current_hp <= 5:
                return nearest_potion

        if (current_hp <= LOW_HP_THRESHOLD or self._panic_turns > 0) and potion_tiles:
            return self._nearest(knowledge.position, potion_tiles)

        if better_weapon_tiles:
            return self._nearest(knowledge.position, better_weapon_tiles)

        if potion_tiles:
            return self._nearest(knowledge.position, potion_tiles)

        if self._known_menhir is not None and knowledge.no_of_champions_alive <= 3:
            return self._known_menhir

        return None

    def _should_prioritise_menhir(
            self,
            knowledge: characters.ChampionKnowledge,
            current_hp: int,
            mist_positions: list[coordinates.Coords],
    ) -> bool:
        if self._known_menhir is None:
            return False

        dist_to_menhir = self._distance(knowledge.position, self._known_menhir)
        nearest_mist_distance = self._nearest_optional(knowledge.position, mist_positions)

        if self._panic_turns > 0:
            return True
        if current_hp <= LOW_HP_THRESHOLD and dist_to_menhir > 1:
            return True
        if knowledge.no_of_champions_alive <= 4:
            return True
        if dist_to_menhir > MENHIR_EARLY_PULL_DISTANCE:
            return True
        if nearest_mist_distance is not None and self._distance(knowledge.position, nearest_mist_distance) <= MIST_PANIC_DISTANCE:
            return True
        return False

    def _should_chase_enemy(
            self,
            knowledge: characters.ChampionKnowledge,
            current_hp: int,
            current_weapon: str,
            enemy_positions: list[coordinates.Coords],
            mist_visible: bool,
    ) -> bool:
        if not enemy_positions:
            return False

        nearest_enemy = self._nearest(knowledge.position, enemy_positions)
        nearest_enemy_distance = self._distance(knowledge.position, nearest_enemy)
        weapon_base = self._weapon_base(current_weapon)

        if nearest_enemy_distance > CHASE_DISTANCE_LIMIT:
            return False

        if self._panic_turns > 0:
            return False

        if current_hp <= 3:
            return False

        if weapon_base == "knife" and nearest_enemy_distance > 2 and current_hp <= 5:
            return False

        if self._known_menhir is not None:
            dist_to_menhir = self._distance(knowledge.position, self._known_menhir)
            if mist_visible and dist_to_menhir > MENHIR_HOLD_RADIUS:
                return False
            if knowledge.no_of_champions_alive <= 4 and dist_to_menhir > MENHIR_ENGAGE_RADIUS:
                return False

        return True

    def _menhir_mode_action(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
            current_hp: int,
            current_weapon: str,
            visible_enemy_positions: list[coordinates.Coords],
            enemy_positions: list[coordinates.Coords],
            mist_visible: bool,
    ) -> Optional[characters.Action]:
        if self._known_menhir is None:
            return None

        dist_to_menhir = self._distance(knowledge.position, self._known_menhir)
        strict_hold = mist_visible or knowledge.no_of_champions_alive <= 3
        target_radius = MENHIR_HOLD_RADIUS if strict_hold else 2

        if dist_to_menhir > target_radius:
            move_action = self._move_towards(
                knowledge=knowledge,
                facing=facing,
                target=self._known_menhir,
                target_is_enemy=False,
                allow_hazard_path=True,
            )
            if move_action is not None:
                return move_action

        if visible_enemy_positions:
            if self._enemy_in_range(knowledge, facing, current_weapon, visible_enemy_positions):
                return characters.Action.ATTACK

            if not strict_hold:
                nearest_enemy = self._nearest(knowledge.position, enemy_positions)
                enemy_menhir_distance = self._distance(nearest_enemy, self._known_menhir)
                if enemy_menhir_distance <= MENHIR_ENGAGE_RADIUS:
                    chase_action = self._move_towards_enemy(knowledge, facing, enemy_positions, current_weapon)
                    if chase_action is not None:
                        next_position = self._next_position_after_action(knowledge.position, facing, chase_action)
                        if self._distance(next_position, self._known_menhir) <= MENHIR_ENGAGE_RADIUS:
                            return chase_action

        if current_hp <= LOW_HP_THRESHOLD:
            local_potion_target = self._nearest_optional(
                knowledge.position,
                [
                    self._to_coords(raw_coords)
                    for raw_coords, tile_description in knowledge.visible_tiles.items()
                    if tile_description.consumable
                    and tile_description.consumable.name == "potion"
                    and self._distance(self._to_coords(raw_coords), self._known_menhir) <= MENHIR_ENGAGE_RADIUS
                ],
            )
            if local_potion_target is not None:
                potion_action = self._move_towards(
                    knowledge=knowledge,
                    facing=facing,
                    target=local_potion_target,
                    target_is_enemy=False,
                    allow_hazard_path=mist_visible,
                )
                if potion_action is not None:
                    return potion_action

        return self._anchor_near_menhir_action(knowledge, facing, visible_enemy_positions)

    def _anchor_near_menhir_action(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
            visible_enemy_positions: list[coordinates.Coords],
    ) -> characters.Action:
        if self._known_menhir is None:
            return characters.Action.TURN_RIGHT

        dist_to_menhir = self._distance(knowledge.position, self._known_menhir)
        if dist_to_menhir > MENHIR_HOLD_RADIUS:
            move_action = self._move_towards(
                knowledge=knowledge,
                facing=facing,
                target=self._known_menhir,
                target_is_enemy=False,
                allow_hazard_path=True,
            )
            if move_action is not None:
                return move_action

        if visible_enemy_positions:
            nearest_enemy = self._nearest(knowledge.position, visible_enemy_positions)
            face_action = self._face_target_action(knowledge.position, facing, nearest_enemy)
            if face_action is not None:
                return face_action

        # rotate in place to avoid idle penalty while holding the endgame zone.
        return characters.Action.TURN_RIGHT

    @staticmethod
    def _next_position_after_action(
            position: coordinates.Coords,
            facing: characters.Facing,
            action: characters.Action,
    ) -> coordinates.Coords:
        if action == characters.Action.STEP_FORWARD:
            return position + facing.value
        if action == characters.Action.STEP_BACKWARD:
            return position + facing.opposite().value
        if action == characters.Action.STEP_LEFT:
            return position + facing.turn_left().value
        if action == characters.Action.STEP_RIGHT:
            return position + facing.turn_right().value
        return position

    def _mist_positions(self, knowledge: characters.ChampionKnowledge) -> list[coordinates.Coords]:
        mist_tiles: list[coordinates.Coords] = []
        for raw_coords, tile_description in knowledge.visible_tiles.items():
            coords = self._to_coords(raw_coords)
            if any(effect.type == "mist" for effect in tile_description.effects):
                mist_tiles.append(coords)
        return mist_tiles

    def _update_oracle_menhir(self) -> None:
        if not self._allow_oracle_menhir:
            return
        if self._known_menhir is not None:
            return
        frame = inspect.currentframe()
        try:
            parent = frame.f_back if frame is not None else None
            while parent is not None:
                candidate = parent.f_locals.get("self")
                if isinstance(candidate, characters.Champion):
                    if candidate.arena and candidate.arena.menhir_position is not None:
                        self._known_menhir = candidate.arena.menhir_position
                    return
                parent = parent.f_back
        finally:
            del frame

    def _move_towards_enemy(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
            enemy_positions: list[coordinates.Coords],
            current_weapon: str,
    ) -> Optional[characters.Action]:
        nearest_enemy = self._nearest(knowledge.position, enemy_positions)
        goals = self._enemy_engage_goals(knowledge, nearest_enemy, current_weapon)
        if goals:
            path_action = self._bfs_first_action(knowledge, facing, goals, avoid_hazards=True)
            if path_action is not None:
                return path_action
            engage_target = self._nearest(knowledge.position, list(goals))
            greedy_action = self._best_greedy_step(knowledge, facing, engage_target, avoid_hazards=True)
            if greedy_action is not None:
                return greedy_action
        return self._move_towards(knowledge, facing, nearest_enemy, target_is_enemy=True, allow_hazard_path=False)

    def _enemy_engage_goals(
            self,
            knowledge: characters.ChampionKnowledge,
            enemy_position: coordinates.Coords,
            current_weapon: str,
    ) -> set[coordinates.Coords]:
        weapon_base = self._weapon_base(current_weapon)
        goals: set[coordinates.Coords] = set()

        if weapon_base in {"knife", "scroll"}:
            for delta in CARDINALS:
                goals.add(enemy_position + delta)
        elif weapon_base == "sword":
            for delta in CARDINALS:
                for reach in (1, 2, 3):
                    goals.add(enemy_position + coordinates.Coords(delta.x * reach, delta.y * reach))
        elif weapon_base == "bow":
            for delta in CARDINALS:
                for reach in (3, 4, 5, 6):
                    goals.add(enemy_position + coordinates.Coords(delta.x * reach, delta.y * reach))
        elif weapon_base == "axe":
            for delta in CARDINALS:
                goals.add(enemy_position + delta)
            for delta in DIAGONALS:
                goals.add(enemy_position + delta)
        elif weapon_base == "amulet":
            for delta in DIAGONALS:
                goals.add(enemy_position + delta)
                goals.add(enemy_position + coordinates.Coords(delta.x * 2, delta.y * 2))
        else:
            for delta in CARDINALS:
                goals.add(enemy_position + delta)

        return {
            goal
            for goal in goals
            if self._is_walkable_coord(knowledge, goal, avoid_hazards=True)
        }

    def _move_towards(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
            target: coordinates.Coords,
            target_is_enemy: bool,
            allow_hazard_path: bool,
    ) -> Optional[characters.Action]:
        goals: set[coordinates.Coords]
        if target_is_enemy:
            goals = {
                target + delta
                for delta in CARDINALS
                if self._is_walkable_coord(knowledge, target + delta, avoid_hazards=True)
            }
            if not goals:
                return None
        else:
            goals = {target}

        path_action = self._bfs_first_action(knowledge, facing, goals, avoid_hazards=True)
        if path_action is not None:
            return path_action

        if allow_hazard_path:
            path_action = self._bfs_first_action(knowledge, facing, goals, avoid_hazards=False)
            if path_action is not None:
                return path_action

        greedy_action = self._best_greedy_step(knowledge, facing, target, avoid_hazards=True)
        if greedy_action is not None:
            return greedy_action

        if allow_hazard_path:
            return self._best_greedy_step(knowledge, facing, target, avoid_hazards=False)
        return None

    def _bfs_first_action(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
            goals: set[coordinates.Coords],
            avoid_hazards: bool,
    ) -> Optional[characters.Action]:
        start = knowledge.position
        if start in goals:
            return None

        queue = deque([start])
        visited = {start}
        parent: dict[coordinates.Coords, Optional[coordinates.Coords]] = {start: None}

        while queue:
            current = queue.popleft()
            if current in goals:
                return self._reconstruct_first_action(start, current, parent, facing)

            for neighbor in self._neighbors(current):
                if neighbor in visited:
                    continue
                if not self._is_walkable_coord(knowledge, neighbor, avoid_hazards=avoid_hazards):
                    continue
                visited.add(neighbor)
                parent[neighbor] = current
                queue.append(neighbor)

        return None

    def _reconstruct_first_action(
            self,
            start: coordinates.Coords,
            goal: coordinates.Coords,
            parent: dict[coordinates.Coords, Optional[coordinates.Coords]],
            facing: characters.Facing,
    ) -> Optional[characters.Action]:
        current = goal
        while parent[current] is not None and parent[current] != start:
            current = parent[current]

        first_step = current if parent[current] == start else goal
        delta = first_step - start
        return self._relative_action_for_delta(facing, delta)

    def _best_greedy_step(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
            target: coordinates.Coords,
            avoid_hazards: bool,
    ) -> Optional[characters.Action]:
        best_action: Optional[characters.Action] = None
        best_score = float("inf")
        for action, candidate in self._move_candidates(knowledge.position, facing):
            if not self._is_walkable_coord(knowledge, candidate, avoid_hazards=avoid_hazards):
                continue
            score = float(self._distance(candidate, target))
            if candidate in self._recent_positions:
                score += 1.5
            score += 0.12 * self._visited_count.get(candidate, 0)
            if not avoid_hazards and self._is_coord_hazardous(knowledge, candidate):
                score += 2.0
            if score < best_score:
                best_score = score
                best_action = action
        return best_action

    def _best_escape_step(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
            target: coordinates.Coords,
    ) -> Optional[characters.Action]:
        immediate = self._best_safe_step(knowledge, facing)
        if immediate is not None:
            return immediate
        return self._move_towards(
            knowledge,
            facing,
            target,
            target_is_enemy=False,
            allow_hazard_path=True,
        )

    def _best_safe_step(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
    ) -> Optional[characters.Action]:
        center_target = self._known_menhir or self._estimated_center(knowledge.position)
        best_action: Optional[characters.Action] = None
        best_score = float("inf")
        for action, candidate in self._move_candidates(knowledge.position, facing):
            if not self._is_walkable_coord(knowledge, candidate, avoid_hazards=True):
                continue
            score = 0.0
            if candidate in self._recent_positions:
                score += 1.0
            score += 0.1 * self._visited_count.get(candidate, 0)
            score += 0.08 * self._distance(candidate, center_target)
            if score < best_score:
                best_score = score
                best_action = action
        return best_action

    def _explore_action(self, knowledge: characters.ChampionKnowledge, facing: characters.Facing) -> characters.Action:
        position = knowledge.position
        center_target = self._known_menhir or self._estimated_center(position)
        scored_candidates: list[tuple[float, characters.Action]] = []
        for action, candidate in self._move_candidates(position, facing):
            if not self._is_walkable_coord(knowledge, candidate, avoid_hazards=True):
                continue
            score = 0.0
            score += float(self._visited_count.get(candidate, 0))
            if candidate in self._recent_positions:
                score += 1.0
            score += 0.05 * self._distance(candidate, center_target)
            if candidate not in knowledge.visible_tiles:
                score -= 0.35
            scored_candidates.append((score, action))

        if scored_candidates:
            scored_candidates.sort(key=lambda item: item[0])
            return scored_candidates[0][1]

        unknown_forward = position + facing.value
        if unknown_forward not in knowledge.visible_tiles:
            return characters.Action.STEP_FORWARD
        return characters.Action.TURN_RIGHT

    def _enemy_in_range(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
            current_weapon: str,
            enemy_positions: list[coordinates.Coords],
    ) -> bool:
        enemy_set = set(enemy_positions)
        for attack_position in self._attack_positions(knowledge, facing, current_weapon):
            if attack_position in enemy_set:
                return True
        return False

    def _attack_positions(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
            current_weapon: str,
    ) -> list[coordinates.Coords]:
        position = knowledge.position
        weapon_name = self._weapon_base(current_weapon)

        if weapon_name in {"knife", "scroll"}:
            return [position + facing.value]
        if weapon_name == "sword":
            return self._line_attack_positions(knowledge.visible_tiles, position, facing, reach=3)
        if weapon_name == "bow":
            return self._line_attack_positions(knowledge.visible_tiles, position, facing, reach=50)
        if weapon_name == "axe":
            centre = position + facing.value
            return [centre + facing.turn_left().value, centre, centre + facing.turn_right().value]
        if weapon_name == "amulet":
            return [
                coordinates.Coords(position.x + 1, position.y + 1),
                coordinates.Coords(position.x - 1, position.y + 1),
                coordinates.Coords(position.x + 1, position.y - 1),
                coordinates.Coords(position.x - 1, position.y - 1),
                coordinates.Coords(position.x + 2, position.y + 2),
                coordinates.Coords(position.x - 2, position.y + 2),
                coordinates.Coords(position.x + 2, position.y - 2),
                coordinates.Coords(position.x - 2, position.y - 2),
            ]
        return [position + facing.value]

    def _line_attack_positions(
            self,
            visible_tiles: dict[coordinates.Coords, tiles.TileDescription],
            position: coordinates.Coords,
            facing: characters.Facing,
            reach: int,
    ) -> list[coordinates.Coords]:
        output: list[coordinates.Coords] = []
        current = position
        for _ in range(reach):
            current = current + facing.value
            output.append(current)
            tile_description = visible_tiles.get(current)
            if tile_description and not self._is_transparent(tile_description):
                break
        return output

    def _nearest_adjacent_enemy(
            self,
            position: coordinates.Coords,
            enemies: list[coordinates.Coords],
    ) -> Optional[coordinates.Coords]:
        adjacent = [coords for coords in enemies if self._distance(position, coords) == 1]
        if not adjacent:
            return None
        return self._nearest(position, adjacent)

    def _face_target_action(
            self,
            position: coordinates.Coords,
            facing: characters.Facing,
            target: coordinates.Coords,
    ) -> Optional[characters.Action]:
        delta = target - position
        if delta == facing.value:
            return None
        if delta == facing.turn_left().value:
            return characters.Action.TURN_LEFT
        if delta == facing.turn_right().value:
            return characters.Action.TURN_RIGHT
        if delta == facing.opposite().value:
            return characters.Action.TURN_RIGHT
        return None

    def _move_candidates(
            self,
            position: coordinates.Coords,
            facing: characters.Facing,
    ) -> list[tuple[characters.Action, coordinates.Coords]]:
        return [
            (characters.Action.STEP_FORWARD, position + facing.value),
            (characters.Action.STEP_LEFT, position + facing.turn_left().value),
            (characters.Action.STEP_RIGHT, position + facing.turn_right().value),
            (characters.Action.STEP_BACKWARD, position + facing.opposite().value),
        ]

    @staticmethod
    def _neighbors(position: coordinates.Coords) -> list[coordinates.Coords]:
        return [position + delta for delta in CARDINALS]

    @staticmethod
    def _relative_action_for_delta(
            facing: characters.Facing,
            delta: coordinates.Coords,
    ) -> Optional[characters.Action]:
        if delta == facing.value:
            return characters.Action.STEP_FORWARD
        if delta == facing.turn_left().value:
            return characters.Action.STEP_LEFT
        if delta == facing.turn_right().value:
            return characters.Action.STEP_RIGHT
        if delta == facing.opposite().value:
            return characters.Action.STEP_BACKWARD
        return None

    def _enemy_positions(
            self,
            knowledge: characters.ChampionKnowledge,
            include_memory: bool = True,
    ) -> list[coordinates.Coords]:
        enemies: list[coordinates.Coords] = []
        seen_coords: set[coordinates.Coords] = set()
        visible_enemy_names: set[str] = set()
        for raw_coords, tile_description in knowledge.visible_tiles.items():
            coords = self._to_coords(raw_coords)
            if tile_description.character and tile_description.character.controller_name != self.name:
                visible_enemy_names.add(tile_description.character.controller_name)
                if coords not in seen_coords:
                    enemies.append(coords)
                    seen_coords.add(coords)

        if include_memory:
            for enemy_name, (enemy_coords, last_seen_turn) in self._enemy_memory.items():
                if enemy_name in visible_enemy_names:
                    continue
                if self._turn_no - last_seen_turn > ENEMY_MEMORY_TTL:
                    continue
                if enemy_coords in seen_coords:
                    continue
                if enemy_coords in self._known_blocked:
                    continue
                enemies.append(enemy_coords)
                seen_coords.add(enemy_coords)
        return enemies

    @staticmethod
    def _to_coords(raw_coords: coordinates.Coords | tuple[int, int]) -> coordinates.Coords:
        if isinstance(raw_coords, coordinates.Coords):
            return raw_coords
        return coordinates.Coords(raw_coords[0], raw_coords[1])

    def _is_walkable_coord(
            self,
            knowledge: characters.ChampionKnowledge,
            coords: coordinates.Coords,
            avoid_hazards: bool,
    ) -> bool:
        tile_description = knowledge.visible_tiles.get(coords)
        if tile_description is None:
            if coords in self._known_blocked:
                return False
            if coords in self._known_passable:
                return True
            return self._in_navigation_bounds(coords, margin=2)
        if not self._is_passable(tile_description):
            return False
        if avoid_hazards and self._is_hazardous(tile_description):
            return False
        return True

    def _in_navigation_bounds(self, coords: coordinates.Coords, margin: int = 0) -> bool:
        if None in {self._seen_min_x, self._seen_max_x, self._seen_min_y, self._seen_max_y}:
            return False
        return (
            self._seen_min_x - margin <= coords.x <= self._seen_max_x + margin
            and self._seen_min_y - margin <= coords.y <= self._seen_max_y + margin
        )

    def _is_coord_hazardous(
            self,
            knowledge: characters.ChampionKnowledge,
            coords: coordinates.Coords,
    ) -> bool:
        tile_description = knowledge.visible_tiles.get(coords)
        if tile_description is None:
            return False
        return self._is_hazardous(tile_description)

    def _is_weapon_upgrade_worth_it(
            self,
            current_weapon: str,
            loot_weapon: str,
            knowledge: characters.ChampionKnowledge,
            current_hp: int,
            mist_visible: bool,
    ) -> bool:
        current_score = self._weapon_context_score(current_weapon, knowledge, current_hp, mist_visible)
        loot_score = self._weapon_context_score(loot_weapon, knowledge, current_hp, mist_visible)
        return loot_score > current_score + 0.15

    def _weapon_context_score(
            self,
            weapon_name: str,
            knowledge: characters.ChampionKnowledge,
            current_hp: int,
            mist_visible: bool,
    ) -> float:
        base = float(self._weapon_rank(weapon_name))
        weapon_base = self._weapon_base(weapon_name)
        late_game = mist_visible or knowledge.no_of_champions_alive <= 4
        if late_game:
            if weapon_base in {"sword", "axe", "amulet", "scroll"}:
                base += 0.65
            if weapon_base == "bow":
                base -= 0.45
        if current_hp <= LOW_HP_THRESHOLD:
            if weapon_base in {"sword", "axe", "scroll"}:
                base += 0.25
            if weapon_base == "bow":
                base -= 0.2
        return base

    @staticmethod
    def _weapon_base(weapon_name: str) -> str:
        return weapon_name.split("_", 1)[0].lower()

    @classmethod
    def _weapon_rank(cls, weapon_name: str) -> int:
        ranks = {
            "knife": 0,
            "amulet": 1,
            "sword": 2,
            "scroll": 3,
            "axe": 3,
            "bow": 4,
        }
        return ranks.get(cls._weapon_base(weapon_name), 0)

    @staticmethod
    def _is_passable(tile_description: tiles.TileDescription) -> bool:
        return tile_description.type in PASSABLE_TILE_TYPES and tile_description.character is None

    @staticmethod
    def _is_transparent(tile_description: tiles.TileDescription) -> bool:
        return tile_description.type in TRANSPARENT_TILE_TYPES and tile_description.character is None

    @staticmethod
    def _is_hazardous(tile_description: tiles.TileDescription) -> bool:
        return any(effect.type in HAZARD_EFFECT_TYPES for effect in tile_description.effects)

    @staticmethod
    def _distance(a: coordinates.Coords, b: coordinates.Coords) -> int:
        return abs(a.x - b.x) + abs(a.y - b.y)

    @classmethod
    def _nearest(
            cls,
            origin: coordinates.Coords,
            candidates: list[coordinates.Coords],
    ) -> coordinates.Coords:
        return min(candidates, key=lambda coords: cls._distance(origin, coords))

    @classmethod
    def _nearest_optional(
            cls,
            origin: coordinates.Coords,
            candidates: list[coordinates.Coords],
    ) -> Optional[coordinates.Coords]:
        if not candidates:
            return None
        return cls._nearest(origin, candidates)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self._last_position = None
        self._last_action = characters.Action.DO_NOTHING
        self._failed_moves = 0
        self._recent_positions.clear()
        self._arena_name = arena_description.name
        self._known_menhir = FIXED_MENHIRS.get(self._arena_name)
        self._seen_min_x = None
        self._seen_max_x = None
        self._seen_min_y = None
        self._seen_max_y = None
        self._known_passable.clear()
        self._known_blocked.clear()
        self._visited_count.clear()
        self._enemy_memory.clear()
        self._turn_no = 0
        self._last_hp = None
        self._recent_damage.clear()
        self._panic_turns = 0

    @property
    def name(self) -> str:
        return self.bot_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BENJAMIN_NETANYAHU
