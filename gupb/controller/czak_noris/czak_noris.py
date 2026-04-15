from collections import deque
from typing import Dict, List, Optional, Tuple

from gupb import controller
from gupb.model import arenas, characters, coordinates, tiles

Facing = characters.Facing
Action = characters.Action
Coords = coordinates.Coords


WEAPON_PRIORITY = {
    'bow_loaded': 6, 'bow_unloaded': 5, 'bow': 5,
    'sword': 5, 'axe': 4, 'amulet': 3, 'scroll': 2, 'knife': 1,
}

PASSABLE_TYPES = {'land', 'forest', 'menhir'}
OPAQUE_TYPES = {'wall', 'forest'}


def _c(t) -> Coords:
    return Coords(t[0], t[1])


def _add(a, b) -> Coords:
    return Coords(a[0] + b[0], a[1] + b[1])


class CzakNoris(controller.Controller):
    def __init__(self, bot_name: str) -> None:
        self.bot_name = bot_name
        self._reset_state()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CzakNoris):
            return self.bot_name == other.bot_name
        return False

    def __hash__(self) -> int:
        return hash(self.bot_name)

    def _reset_state(self) -> None:
        self.known: Dict[Coords, tiles.TileDescription] = {}
        self.menhir: Optional[Coords] = None
        self.tick: int = 0
        self.mist_seen: bool = False

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self._reset_state()
        if arena_description.name in arenas.FIXED_MENHIRS:
            self.menhir = _c(arenas.FIXED_MENHIRS[arena_description.name])

    def praise(self, score: int) -> None:
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.tick += 1
        self._observe(knowledge)
        my_pos = _c(knowledge.position)
        my_tile = knowledge.visible_tiles[knowledge.position]
        my_desc = my_tile.character
        if my_desc is None:
            return Action.TURN_LEFT
        facing = my_desc.facing
        weapon_name = my_desc.weapon.name

        enemies = self._enemies(knowledge)

        if self._can_hit_enemy(my_pos, facing, weapon_name, enemies):
            return Action.ATTACK

        turn = self._turn_to_hit(my_pos, facing, weapon_name, enemies)
        if turn is not None:
            return turn

        target = self._pick_target(my_pos, weapon_name, enemies, my_desc.health)
        if target is not None and target != my_pos:
            action = self._step_towards(my_pos, facing, target)
            if action is not None:
                return action

        return Action.TURN_RIGHT

    def _observe(self, knowledge: characters.ChampionKnowledge) -> None:
        for coord, desc in knowledge.visible_tiles.items():
            ck = _c(coord)
            self.known[ck] = desc
            if desc.type == 'menhir':
                self.menhir = ck
            for eff in desc.effects:
                if eff.type == 'mist':
                    self.mist_seen = True

    def _enemies(self, knowledge: characters.ChampionKnowledge) -> List[Tuple[Coords, characters.ChampionDescription]]:
        out = []
        for coord, desc in knowledge.visible_tiles.items():
            if desc.character and desc.character.controller_name != self.bot_name:
                out.append((_c(coord), desc.character))
        return out

    def _attack_tiles(self, pos: Coords, facing: Facing, weapon_name: str) -> List[Coords]:
        wn = 'bow' if weapon_name.startswith('bow') else weapon_name
        fv = facing.value
        if wn in ('knife', 'scroll'):
            return self._line(pos, facing, 1)
        if wn == 'sword':
            return self._line(pos, facing, 3)
        if wn == 'bow':
            return self._line(pos, facing, 50)
        if wn == 'axe':
            centre = _add(pos, fv)
            lv = facing.turn_left().value
            rv = facing.turn_right().value
            return [_add(centre, lv), centre, _add(centre, rv)]
        if wn == 'amulet':
            px, py = pos[0], pos[1]
            return [
                Coords(px + 1, py + 1), Coords(px - 1, py + 1),
                Coords(px + 1, py - 1), Coords(px - 1, py - 1),
                Coords(px + 2, py + 2), Coords(px - 2, py + 2),
                Coords(px + 2, py - 2), Coords(px - 2, py - 2),
            ]
        return self._line(pos, facing, 1)

    def _line(self, pos: Coords, facing: Facing, reach: int) -> List[Coords]:
        out = []
        cur = pos
        fv = facing.value
        for _ in range(reach):
            cur = _add(cur, fv)
            if cur not in self.known:
                break
            out.append(cur)
            if self.known[cur].type in OPAQUE_TYPES:
                break
        return out

    def _can_hit_enemy(self, pos: Coords, facing: Facing, weapon_name: str,
                       enemies: List[Tuple[Coords, characters.ChampionDescription]]) -> bool:
        if not enemies:
            return False
        if weapon_name == 'bow_unloaded':
            return False
        enemy_coords = {ec for ec, _ in enemies}
        tiles_hit = set(self._attack_tiles(pos, facing, weapon_name))
        return bool(enemy_coords & tiles_hit)

    def _turn_to_hit(self, pos: Coords, facing: Facing, weapon_name: str,
                     enemies: List[Tuple[Coords, characters.ChampionDescription]]) -> Optional[Action]:
        if not enemies:
            return None
        enemy_coords = {ec for ec, _ in enemies}
        left = facing.turn_left()
        right = facing.turn_right()
        if enemy_coords & set(self._attack_tiles(pos, left, weapon_name)):
            return Action.TURN_LEFT
        if enemy_coords & set(self._attack_tiles(pos, right, weapon_name)):
            return Action.TURN_RIGHT
        if enemy_coords & set(self._attack_tiles(pos, facing.opposite(), weapon_name)):
            return Action.TURN_LEFT
        return None

    def _pick_target(self, pos: Coords, weapon_name: str,
                     enemies: List[Tuple[Coords, characters.ChampionDescription]],
                     my_hp: int) -> Optional[Coords]:
        my_prio = WEAPON_PRIORITY.get(weapon_name, 1)

        if my_hp <= 4:
            potion = self._nearest(pos, lambda d: d.consumable and d.consumable.name == 'potion')
            if potion is not None:
                return potion

        if my_prio <= 3:
            better = self._nearest(pos, lambda d: d.loot and WEAPON_PRIORITY.get(d.loot.name, 0) > my_prio)
            if better is not None:
                return better

        if self.mist_seen or self.tick > 80:
            if self.menhir is not None:
                return self.menhir

        if enemies and my_prio >= 3:
            return min((ec for ec, _ in enemies),
                       key=lambda c: abs(c[0] - pos[0]) + abs(c[1] - pos[1]))

        if self.menhir is not None:
            return self.menhir

        return self._frontier(pos)

    def _nearest(self, pos: Coords, predicate) -> Optional[Coords]:
        best = None
        best_d = 10 ** 9
        for c, d in self.known.items():
            if predicate(d):
                dist = abs(c[0] - pos[0]) + abs(c[1] - pos[1])
                if dist < best_d:
                    best_d = dist
                    best = c
        return best

    def _frontier(self, pos: Coords) -> Optional[Coords]:
        best = None
        best_d = 10 ** 9
        for c, d in self.known.items():
            if d.type not in PASSABLE_TYPES:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = Coords(c[0] + dx, c[1] + dy)
                if n not in self.known:
                    dist = abs(c[0] - pos[0]) + abs(c[1] - pos[1])
                    if dist < best_d:
                        best_d = dist
                        best = c
                    break
        return best

    def _step_towards(self, pos: Coords, facing: Facing, target: Coords) -> Optional[Action]:
        path = self._bfs(pos, target)
        if not path or len(path) < 2:
            return None
        nxt = path[1]
        dx, dy = nxt[0] - pos[0], nxt[1] - pos[1]
        fv = facing.value
        if (dx, dy) == (fv[0], fv[1]):
            return Action.STEP_FORWARD
        ov = facing.opposite().value
        if (dx, dy) == (ov[0], ov[1]):
            return Action.STEP_BACKWARD
        lv = facing.turn_left().value
        if (dx, dy) == (lv[0], lv[1]):
            return Action.STEP_LEFT
        rv = facing.turn_right().value
        if (dx, dy) == (rv[0], rv[1]):
            return Action.STEP_RIGHT
        return None

    def _bfs(self, start: Coords, goal: Coords) -> List[Coords]:
        if start == goal:
            return [start]
        queue = deque([start])
        parent: Dict[Coords, Coords] = {start: start}
        while queue:
            cur = queue.popleft()
            if cur == goal:
                path = [cur]
                while parent[path[-1]] != path[-1]:
                    path.append(parent[path[-1]])
                path.reverse()
                return path
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = Coords(cur[0] + dx, cur[1] + dy)
                if n in parent:
                    continue
                d = self.known.get(n)
                if d is None:
                    if n != goal:
                        continue
                elif d.type not in PASSABLE_TYPES:
                    continue
                elif d.character is not None and n != goal:
                    continue
                parent[n] = cur
                queue.append(n)
        return []

    @property
    def name(self) -> str:
        return self.bot_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.CZAK_NORIS
