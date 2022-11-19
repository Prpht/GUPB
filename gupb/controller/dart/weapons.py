from typing import List, Optional, Tuple
from gupb.controller.dart.movement_mechanics import MapKnowledge, get_facing, is_opponent_at_coords, manhattan_distance
from gupb.model.arenas import Terrain
from gupb.model.characters import ChampionKnowledge, Facing
from gupb.model.coordinates import Coords

from gupb.model.weapons import Amulet, Axe, Bow, Knife, LineWeapon, Sword, Weapon


class WeaponWrapper(Weapon):
    def __init__(self, terrain: Terrain) -> None:
        super().__init__()
        self._terrain = terrain

    @property
    def _attack_positions(self) -> List[Tuple[int, int]]:
        raise NotImplementedError()

    def can_attack(self,
                   knowledge: ChampionKnowledge,
                   opponent_position: Coords,
                   facing: Optional[Facing] = None) -> bool:
        facing = facing if facing is not None else get_facing(knowledge)
        weapon_cut_positions = self.cut_positions(self._terrain, knowledge.position, facing)
        return is_opponent_at_coords(opponent_position, knowledge.visible_tiles) and \
            opponent_position in weapon_cut_positions

    def is_any_opponent_in_range(self, knowledge: ChampionKnowledge, opponents: List[Coords]) -> bool:
        return any(self.can_attack(knowledge, pos) for pos in opponents)

    def get_facing_for_attack(self, knowledge: ChampionKnowledge, opponent_position: Coords) -> Optional[Facing]:
        for facing in Facing:
            if self.can_attack(knowledge, opponent_position, facing):
                return facing
        return None

    def get_facings_for_attack(sekf, position: Coords, opponent_position: Coords) -> List[Facing]:
        dx, dy = opponent_position - position
        dx = 0 if dx == 0 else dx // abs(dx)
        dy = 0 if dy == 0 else dy // abs(dy)
        if dx != 0 and dy != 0:
            return [Facing(Coords(0, dy)), Facing(Coords(dx, 0))]
        return [Facing(Coords(dx, dy))]

    def get_attack_positions(self, map_knowledge: MapKnowledge, opponent_position: Coords) -> List[Coords]:
        x, y = opponent_position
        pos = []
        for dx, dy in self._attack_positions:
            new_x = x + dx
            new_y = y + dy
            if new_x < 0 or new_y < 0 or new_x >= map_knowledge.arena.size[0] or new_y >= map_knowledge.arena.size[1]:
                continue
            new_pos = Coords(new_x, new_y)
            new_facing = self.get_facings_for_attack(new_pos, opponent_position)[0]
            if map_knowledge.is_land(new_pos) and opponent_position in self.cut_positions(
                    self._terrain, new_pos, new_facing):
                pos.append(new_pos)
        return pos

    def get_best_attack_position(self,
                                 knowledge: ChampionKnowledge,
                                 map_knowledge: MapKnowledge,
                                 opponent_position: Coords) -> Coords:
        positions = self.get_attack_positions(map_knowledge, opponent_position)
        return min(positions, key=lambda p: manhattan_distance(knowledge.position, p))


class LineWrapper(WeaponWrapper, LineWeapon):
    @property
    def _attack_positions(self) -> List[Tuple[int, int]]:
        return [(i * x, i * y) for x, y in [(0, 1), (0, -1), (1, 0), (-1, 0)] for i in range(1, self.reach() + 1)]


class KnifeWrapper(LineWrapper, Knife):
    ...


class SwordWrapper(LineWrapper, Sword):
    ...


class BowWrapper(LineWrapper, Bow):
    ...


class AxeWrapper(WeaponWrapper, Axe):
    @property
    def _attack_positions(self) -> List[Tuple[int, int]]:
        return [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]


class AmuletWrapper(WeaponWrapper, Amulet):
    @property
    def _attack_positions(self) -> List[Tuple[int, int]]:
        return [(i * x, i * y) for x, y in [(1, -1), (1, 1), (-1, 1), (-1, -1)] for i in range(1, 3)]


def get_champion_weapon(knowledge: ChampionKnowledge) -> str:
    return knowledge.visible_tiles[knowledge.position].character.weapon.name


def get_weapon(weapon_name: str, terrain: Terrain) -> WeaponWrapper:
    if weapon_name == "knife":
        return KnifeWrapper(terrain)
    if weapon_name == "sword":
        return SwordWrapper(terrain)
    if weapon_name.startswith("bow"):
        return BowWrapper(terrain)
    if weapon_name == "axe":
        return AxeWrapper(terrain)
    if weapon_name == "amulet":
        return AmuletWrapper(terrain)
