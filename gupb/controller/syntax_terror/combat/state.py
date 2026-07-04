from typing import NamedTuple

from gupb.model import characters, coordinates

from ..utils import is_visible
from ..weapons import (
    weapon_max_range as _get_weapon_max_range,
    attack_damage as _attack_damage,
    parse_weapon,
)
from gupb.model.characters import CHAMPION_STARTING_HP
from gupb.model.consumables import POTION_RESTORED_HP
from .arena import CombatArena, _attack_cells

_SCROLL_CHARGE_VALUE: float = 50.0
_HP_REF: float = float(CHAMPION_STARTING_HP * 2)
_HP_COMFORT: float = float(CHAMPION_STARTING_HP - POTION_RESTORED_HP)


class CombatPlayer(NamedTuple):
    pos: coordinates.Coords
    facing: characters.Facing
    hp: int
    weapon: str


class CombatState(NamedTuple):
    me: CombatPlayer
    opp: CombatPlayer
    arena: CombatArena
    me_to_move: bool
    plies: int
    alive_count: int
    menhir_pos: coordinates.Coords | None = None
    mist_radius: int | None = None
    mist_tick_counter: int = 0
    extra_fire: tuple[coordinates.Coords, ...] = ()
    potions: frozenset[coordinates.Coords] = frozenset()
    loot: tuple[tuple[coordinates.Coords, str], ...] = ()
    mist_seen: frozenset[coordinates.Coords] | set[coordinates.Coords] = frozenset()

    @property
    def is_terminal(self) -> bool:
        return self.me.hp <= 0 or self.opp.hp <= 0

    def evaluate(self) -> float:
        if self.me.hp <= 0:
            return -100000.0 * (0.99 ** self.plies)

        if self.opp.hp <= 0:
            base_score = 64000.0 - (max(0.0, _HP_COMFORT - self.me.hp)) ** 2
        else:
            reward_weight = max(0.1, self.me.hp / _HP_REF)
            base_score = (
                reward_weight * (_HP_REF - self.opp.hp) ** 3
                - (max(0.0, _HP_COMFORT - self.me.hp)) ** 2
            )

            name, charges = parse_weapon(self.me.weapon)
            if name == "scroll":
                base_score += charges * _SCROLL_CHARGE_VALUE

            blocking = {self.me.pos, self.opp.pos} | self.arena.other_champions
            my_cells = _attack_cells(
                self.me.weapon, self.me.pos, self.me.facing, self.arena, blocking
            )
            opp_cells = _attack_cells(
                self.opp.weapon, self.opp.pos, self.opp.facing, self.arena, blocking
            )

            if self.opp.pos in my_cells:
                d_me = _attack_damage(self.me.weapon)
                base_score += reward_weight * 0.5 * (
                    (_HP_REF - self.opp.hp + d_me) ** 3
                    - (_HP_REF - self.opp.hp) ** 3
                )

            if self.me.pos in opp_cells:
                d_opp = _attack_damage(self.opp.weapon)
                base_score -= 0.5 * (
                    max(0.0, _HP_COMFORT - self.me.hp + d_opp) ** 2
                    - max(0.0, _HP_COMFORT - self.me.hp) ** 2
                )

            opp_range = _get_weapon_max_range(self.opp.weapon)
            my_range = _get_weapon_max_range(self.me.weapon)
            comfort = max(opp_range + 1, my_range)
            dist = abs(self.me.pos[0] - self.opp.pos[0]) + abs(
                self.me.pos[1] - self.opp.pos[1]
            )
            if dist > comfort:
                base_score += 1.0 / (dist + 1.0)
            else:
                base_score += 1.0 / (comfort + 1.0)

            if not is_visible(
                self.me.pos, self.me.facing, self.opp.pos, self.arena.terrain_transparent
            ):
                base_score *= 0.95

        return base_score * (0.99 ** self.plies)
