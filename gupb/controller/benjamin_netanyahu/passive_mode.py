from __future__ import annotations

from typing import Optional

from gupb.controller.benjamin_netanyahu.normal_mode import BenjaminNormalMode
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles

from .shared_state import BenjaminSharedState

CRITICAL_HP = 3
SAFE_MENHIR_RADIUS = 2
ENDGAME_SWITCH_ALIVE = 4
ENDGAME_MIN_HP = 2


class BenjaminPassiveMode(BenjaminNormalMode):
    """
    Coward mode.
    Prefers hiding, retreating, and surviving over fighting.
    """

    def __init__(
            self,
            bot_name: str = "BenjaminPassiveMode",
            shared_state: Optional[BenjaminSharedState] = None,
            allow_oracle_menhir: bool = False,
    ):
        super().__init__(
            bot_name=bot_name,
            shared_state=shared_state,
            allow_oracle_menhir=allow_oracle_menhir,
        )

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

        if self._in_endgame_mode(context.knowledge, context.current_hp, context.mist_visible):
            endgame_action = self._endgame_action(
                knowledge=context.knowledge,
                facing=context.facing,
                current_hp=context.current_hp,
                current_weapon=context.current_weapon,
                visible_enemy_positions=context.visible_enemy_positions,
                enemy_positions=context.enemy_positions,
                mist_visible=context.mist_visible,
                mist_positions=context.mist_positions,
            )
            if endgame_action is not None:
                return self._store_action(endgame_action, context.knowledge.position)

        # Primary behaviour: avoid fight when possible.
        if context.visible_enemy_positions:
            retreat_action = self._retreat_from_enemy(
                knowledge=context.knowledge,
                facing=context.facing,
                enemy_positions=context.visible_enemy_positions,
                prefer_forest=True,
            )
            if retreat_action is not None:
                return self._store_action(retreat_action, context.knowledge.position)

            # If trapped in melee with no retreat, defend.
            adjacent_enemy = self._nearest_adjacent_enemy(context.knowledge.position, context.visible_enemy_positions)
            if adjacent_enemy is not None:
                face_action = self._face_target_action(context.knowledge.position, context.facing, adjacent_enemy)
                if face_action is None:
                    return self._store_action(characters.Action.ATTACK, context.knowledge.position)
                return self._store_action(face_action, context.knowledge.position)

        if self._known_menhir is not None and self._should_prioritise_menhir(
            context.knowledge,
            context.current_hp,
            context.mist_positions,
        ):
            menhir_action = self._coward_menhir_action(
                knowledge=context.knowledge,
                facing=context.facing,
                current_hp=context.current_hp,
                visible_enemy_positions=context.visible_enemy_positions,
                mist_visible=context.mist_visible,
                current_weapon=context.current_weapon,
            )
            if menhir_action is not None:
                return self._store_action(menhir_action, context.knowledge.position)

        target = self._choose_resource_target(
            context.knowledge,
            context.current_hp,
            context.current_weapon,
            context.mist_visible,
        )
        if target is not None:
            move_action = self._move_towards(
                knowledge=context.knowledge,
                facing=context.facing,
                target=target,
                target_is_enemy=False,
                allow_hazard_path=False,
            )
            if move_action is not None:
                return self._store_action(move_action, context.knowledge.position)

        hide_target = self._choose_hide_target(context.knowledge, context.enemy_positions)
        if hide_target is not None:
            if hide_target == context.knowledge.position:
                return self._store_action(
                    self._hold_position_action(context.facing, context.visible_enemy_positions, context.knowledge.position),
                    context.knowledge.position,
                )
            hide_action = self._move_towards(
                knowledge=context.knowledge,
                facing=context.facing,
                target=hide_target,
                target_is_enemy=False,
                allow_hazard_path=False,
            )
            if hide_action is not None:
                return self._store_action(hide_action, context.knowledge.position)

        explore_action = self._explore_action(context.knowledge, context.facing)
        return self._store_action(explore_action, context.knowledge.position)

    @staticmethod
    def _in_endgame_mode(
            knowledge: characters.ChampionKnowledge,
            current_hp: int,
            mist_visible: bool,
    ) -> bool:
        if knowledge.no_of_champions_alive <= 2:
            return True
        if knowledge.no_of_champions_alive <= ENDGAME_SWITCH_ALIVE and current_hp >= ENDGAME_MIN_HP:
            return True
        if mist_visible and knowledge.no_of_champions_alive <= 5 and current_hp >= 4:
            return True
        return False

    def _endgame_action(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
            current_hp: int,
            current_weapon: str,
            visible_enemy_positions: list[coordinates.Coords],
            enemy_positions: list[coordinates.Coords],
            mist_visible: bool,
            mist_positions: list[coordinates.Coords],
    ) -> Optional[characters.Action]:
        if visible_enemy_positions:
            adjacent_enemy = self._nearest_adjacent_enemy(knowledge.position, visible_enemy_positions)
            if adjacent_enemy is not None:
                face_action = self._face_target_action(knowledge.position, facing, adjacent_enemy)
                if face_action is None:
                    return characters.Action.ATTACK
                return face_action

            if self._enemy_in_range(knowledge, facing, current_weapon, visible_enemy_positions):
                return characters.Action.ATTACK

        if enemy_positions and self._should_chase_enemy_in_endgame(
            knowledge=knowledge,
            current_hp=current_hp,
            current_weapon=current_weapon,
            enemy_positions=enemy_positions,
            mist_visible=mist_visible,
        ):
            chase_action = self._move_towards_enemy(knowledge, facing, enemy_positions, current_weapon)
            if chase_action is not None:
                return chase_action

        if self._known_menhir is not None and super()._should_prioritise_menhir(
            knowledge=knowledge,
            current_hp=current_hp,
            mist_positions=mist_positions,
        ):
            menhir_action = super()._menhir_mode_action(
                knowledge=knowledge,
                facing=facing,
                current_hp=current_hp,
                current_weapon=current_weapon,
                visible_enemy_positions=visible_enemy_positions,
                enemy_positions=enemy_positions,
                mist_visible=mist_visible,
            )
            if menhir_action is not None:
                return menhir_action

        target = super()._choose_resource_target(
            knowledge=knowledge,
            current_hp=current_hp,
            current_weapon=current_weapon,
            mist_visible=mist_visible,
        )
        if target is not None:
            target_action = self._move_towards(
                knowledge=knowledge,
                facing=facing,
                target=target,
                target_is_enemy=False,
                allow_hazard_path=False,
            )
            if target_action is not None:
                return target_action

        return super()._explore_action(knowledge, facing)

    def _should_chase_enemy(
            self,
            knowledge: characters.ChampionKnowledge,
            current_hp: int,
            current_weapon: str,
            enemy_positions: list[coordinates.Coords],
            mist_visible: bool,
    ) -> bool:
        # CowardBot never chooses proactive chase.
        return False

    def _should_chase_enemy_in_endgame(
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

        if nearest_enemy_distance > 8:
            return False
        if current_hp <= 1 and nearest_enemy_distance > 1:
            return False
        if self._panic_turns > 0 and nearest_enemy_distance > 2:
            return False
        if weapon_base == "knife" and nearest_enemy_distance > 3 and current_hp <= 4:
            return False

        if self._known_menhir is not None:
            dist_to_menhir = self._distance(knowledge.position, self._known_menhir)
            if mist_visible and dist_to_menhir > SAFE_MENHIR_RADIUS + 1:
                return False

        return True

    def _should_prioritise_menhir(
            self,
            knowledge: characters.ChampionKnowledge,
            current_hp: int,
            mist_positions: list[coordinates.Coords],
    ) -> bool:
        if self._known_menhir is None:
            return False

        dist_to_menhir = self._distance(knowledge.position, self._known_menhir)
        nearest_mist = self._nearest_optional(knowledge.position, mist_positions)

        if self._panic_turns > 0:
            return True
        if current_hp <= CRITICAL_HP:
            return True
        if knowledge.no_of_champions_alive <= 4:
            return True
        if dist_to_menhir > SAFE_MENHIR_RADIUS:
            return True
        if nearest_mist is not None and self._distance(knowledge.position, nearest_mist) <= 4:
            return True
        return False

    def _choose_resource_target(
            self,
            knowledge: characters.ChampionKnowledge,
            current_hp: int,
            current_weapon: str,
            mist_visible: bool,
    ) -> Optional[coordinates.Coords]:
        potion_tiles: list[coordinates.Coords] = []
        for raw_coords, tile_description in knowledge.visible_tiles.items():
            coords = self._to_coords(raw_coords)
            if tile_description.consumable and tile_description.consumable.name == "potion":
                potion_tiles.append(coords)

        if potion_tiles and (current_hp <= 5 or self._panic_turns > 0):
            return self._nearest(knowledge.position, potion_tiles)

        if self._known_menhir is not None:
            dist_to_menhir = self._distance(knowledge.position, self._known_menhir)
            if mist_visible or knowledge.no_of_champions_alive <= 4 or dist_to_menhir > SAFE_MENHIR_RADIUS:
                return self._known_menhir

        # Very conservative loot policy: take upgrades only when safe and healthy.
        if current_hp >= 7 and not mist_visible:
            better_weapon_tiles: list[coordinates.Coords] = []
            for raw_coords, tile_description in knowledge.visible_tiles.items():
                coords = self._to_coords(raw_coords)
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
            if better_weapon_tiles:
                return self._nearest(knowledge.position, better_weapon_tiles)

        return None

    def _coward_menhir_action(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
            current_hp: int,
            visible_enemy_positions: list[coordinates.Coords],
            mist_visible: bool,
            current_weapon: str,
    ) -> Optional[characters.Action]:
        if self._known_menhir is None:
            return None

        dist_to_menhir = self._distance(knowledge.position, self._known_menhir)
        if dist_to_menhir > SAFE_MENHIR_RADIUS:
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
            adjacent_enemy = self._nearest_adjacent_enemy(knowledge.position, visible_enemy_positions)
            if adjacent_enemy is not None:
                face_action = self._face_target_action(knowledge.position, facing, adjacent_enemy)
                if face_action is None:
                    return characters.Action.ATTACK
                return face_action

            if self._enemy_in_range(knowledge, facing, current_weapon, visible_enemy_positions):
                return characters.Action.ATTACK

        retreat_action = self._retreat_from_enemy(
            knowledge=knowledge,
            facing=facing,
            enemy_positions=visible_enemy_positions,
            prefer_forest=True,
        )
        if retreat_action is not None:
            return retreat_action

        forest_anchor = self._nearest_forest_near_menhir(knowledge)
        if forest_anchor is not None and forest_anchor != knowledge.position:
            forest_action = self._move_towards(
                knowledge=knowledge,
                facing=facing,
                target=forest_anchor,
                target_is_enemy=False,
                allow_hazard_path=mist_visible,
            )
            if forest_action is not None:
                return forest_action

        if current_hp <= CRITICAL_HP:
            potion_target = self._nearest_optional(
                knowledge.position,
                [
                    self._to_coords(raw_coords)
                    for raw_coords, tile_description in knowledge.visible_tiles.items()
                    if tile_description.consumable and tile_description.consumable.name == "potion"
                ],
            )
            if potion_target is not None:
                potion_action = self._move_towards(
                    knowledge=knowledge,
                    facing=facing,
                    target=potion_target,
                    target_is_enemy=False,
                    allow_hazard_path=mist_visible,
                )
                if potion_action is not None:
                    return potion_action

        return self._hold_position_action(facing, visible_enemy_positions, knowledge.position)

    def _retreat_from_enemy(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
            enemy_positions: list[coordinates.Coords],
            prefer_forest: bool,
    ) -> Optional[characters.Action]:
        if not enemy_positions:
            return None

        safe_anchor = self._known_menhir or self._estimated_center(knowledge.position)
        best_action: Optional[characters.Action] = None
        best_score = float("-inf")

        for action, candidate in self._move_candidates(knowledge.position, facing):
            if not self._is_walkable_coord(knowledge, candidate, avoid_hazards=True):
                continue

            min_enemy_distance = min(self._distance(candidate, enemy_position) for enemy_position in enemy_positions)
            tile_description = knowledge.visible_tiles.get(candidate)
            is_forest = tile_description is not None and tile_description.type == "forest"

            score = 3.0 * float(min_enemy_distance)
            score -= 0.35 * float(self._distance(candidate, safe_anchor))
            score -= 0.11 * float(self._visited_count.get(candidate, 0))
            if candidate in self._recent_positions:
                score -= 0.85
            if is_forest:
                score += 1.35
            if prefer_forest and not is_forest:
                score -= 0.65

            if score > best_score:
                best_score = score
                best_action = action

        return best_action

    def _choose_hide_target(
            self,
            knowledge: characters.ChampionKnowledge,
            enemy_positions: list[coordinates.Coords],
    ) -> Optional[coordinates.Coords]:
        if not knowledge.visible_tiles:
            return None

        safe_anchor = self._known_menhir or self._estimated_center(knowledge.position)
        best_target: Optional[coordinates.Coords] = None
        best_score = float("-inf")

        for raw_coords, tile_description in knowledge.visible_tiles.items():
            coords = self._to_coords(raw_coords)
            if not self._is_walkable_coord(knowledge, coords, avoid_hazards=True) and coords != knowledge.position:
                continue

            enemy_distance = min(
                (self._distance(coords, enemy_position) for enemy_position in enemy_positions),
                default=4,
            )
            is_forest = tile_description.type == "forest"
            score = 2.4 * float(enemy_distance)
            score -= 0.35 * float(self._distance(coords, safe_anchor))
            score -= 0.08 * float(self._visited_count.get(coords, 0))
            if self._known_menhir is not None:
                menhir_distance = self._distance(coords, self._known_menhir)
                if menhir_distance <= SAFE_MENHIR_RADIUS:
                    score += 1.0
                else:
                    score -= 0.2 * float(menhir_distance)
            if is_forest:
                score += 1.6
            if coords == knowledge.position and is_forest:
                score += 0.45
            if coords in self._recent_positions and coords != knowledge.position:
                score -= 0.7

            if score > best_score:
                best_score = score
                best_target = coords

        return best_target

    def _nearest_forest_near_menhir(
            self,
            knowledge: characters.ChampionKnowledge,
    ) -> Optional[coordinates.Coords]:
        if self._known_menhir is None:
            return None
        forests = [
            self._to_coords(raw_coords)
            for raw_coords, tile_description in knowledge.visible_tiles.items()
            if tile_description.type == "forest"
            and self._is_walkable_coord(knowledge, self._to_coords(raw_coords), avoid_hazards=True)
            and self._distance(self._to_coords(raw_coords), self._known_menhir) <= SAFE_MENHIR_RADIUS
        ]
        if not forests:
            return None
        return self._nearest(knowledge.position, forests)

    def _hold_position_action(
            self,
            facing: characters.Facing,
            enemy_positions: list[coordinates.Coords],
            current_position: coordinates.Coords,
    ) -> characters.Action:
        if enemy_positions:
            nearest_enemy = self._nearest(current_position, enemy_positions)
            face_action = self._face_target_action(current_position, facing, nearest_enemy)
            if face_action is not None:
                return face_action
        return characters.Action.TURN_RIGHT

    def _explore_action(
            self,
            knowledge: characters.ChampionKnowledge,
            facing: characters.Facing,
    ) -> characters.Action:
        enemy_positions = self._enemy_positions(knowledge, include_memory=False)
        retreat = self._retreat_from_enemy(
            knowledge=knowledge,
            facing=facing,
            enemy_positions=enemy_positions,
            prefer_forest=False,
        )
        if retreat is not None:
            return retreat
        return super()._explore_action(knowledge, facing)

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BENJAMIN_NETANYAHU
