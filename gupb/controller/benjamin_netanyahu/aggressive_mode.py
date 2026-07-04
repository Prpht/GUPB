from __future__ import annotations

from typing import Optional

from gupb.controller.benjamin_netanyahu.normal_mode import BenjaminNormalMode
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles

from .shared_state import BenjaminSharedState


class BenjaminAggressiveMode(BenjaminNormalMode):
    """
    Aggressive mode.
    Prioritizes chase/fights much harder while keeping enough survival logic
    to avoid instantly feeding in mist.
    """

    def __init__(
            self,
            bot_name: str = "BenjaminAggressiveMode",
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

        # Aggressive priority: chase whenever it is not clearly suicidal.
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

        # If no direct plan, keep pressure by moving toward freshest remembered enemy.
        memory_target = self._fresh_enemy_memory_target(context.knowledge.position)
        if memory_target is not None:
            memory_chase_action = self._move_towards(
                knowledge=context.knowledge,
                facing=context.facing,
                target=memory_target,
                target_is_enemy=False,
                allow_hazard_path=False,
            )
            if memory_chase_action is not None:
                return self._store_action(memory_chase_action, context.knowledge.position)

        explore_action = self._explore_action(context.knowledge, context.facing)
        return self._store_action(explore_action, context.knowledge.position)

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

        if self._panic_turns > 0 and current_hp <= 3:
            return True
        if current_hp <= 2 and dist_to_menhir > 2:
            return True
        if nearest_mist is not None and self._distance(knowledge.position, nearest_mist) <= 3:
            return True
        if knowledge.no_of_champions_alive <= 2 and dist_to_menhir > 3:
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

        if nearest_enemy_distance > 10:
            return False
        if current_hp <= 2 and nearest_enemy_distance > 2:
            return False
        if self._panic_turns > 1 and current_hp <= 3:
            return False
        if mist_visible and self._known_menhir is not None:
            # still avoid chasing too far from safe zone in active mist.
            if self._distance(knowledge.position, self._known_menhir) > 5:
                return False
        if weapon_base == "knife" and nearest_enemy_distance > 3 and current_hp <= 4:
            return False
        return True

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

        # Aggressive preference: weapon upgrades first, potion only at critical HP.
        if current_hp <= 2 and potion_tiles:
            return self._nearest(knowledge.position, potion_tiles)

        if better_weapon_tiles:
            return self._nearest(knowledge.position, better_weapon_tiles)

        if current_hp <= 3 and potion_tiles:
            return self._nearest(knowledge.position, potion_tiles)

        if self._known_menhir is not None and (mist_visible or knowledge.no_of_champions_alive <= 3):
            return self._known_menhir

        if potion_tiles and current_hp <= 4:
            return self._nearest(knowledge.position, potion_tiles)

        return None

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

        if weapon_base in {"sword", "axe", "bow"}:
            base += 0.45
        if weapon_base == "amulet":
            base += 0.2
        if weapon_base == "scroll":
            base += 0.1

        if late_game:
            if weapon_base in {"sword", "axe", "scroll"}:
                base += 0.45
            if weapon_base == "bow":
                base -= 0.25

        if current_hp <= 2 and weapon_base == "bow":
            base -= 0.4
        return base

    def _fresh_enemy_memory_target(self, origin: coordinates.Coords) -> Optional[coordinates.Coords]:
        if not self._enemy_memory:
            return None
        recent_entries = [
            (enemy_coords, last_seen_turn)
            for enemy_coords, last_seen_turn in self._enemy_memory.values()
            if self._turn_no - last_seen_turn <= 4
        ]
        if not recent_entries:
            return None
        return min(recent_entries, key=lambda entry: self._distance(origin, entry[0]))[0]

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BENJAMIN_NETANYAHU
