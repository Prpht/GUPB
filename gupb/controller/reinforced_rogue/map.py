import logging

from math import inf
from typing import Optional
from queue import PriorityQueue
from collections import defaultdict

from gupb.model import tiles
from gupb.model import arenas
from gupb.model import weapons
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import consumables

from .constants import *
from .utils import manhattan_dist

logger = logging.getLogger("verbose")


class Map:
    def __init__(self, arena_description: arenas.ArenaDescription):
        self._arena = arenas.Arena.load(name := arena_description.name)
        self._enemy_coords: dict[str, coordinates.Coords] = {}

        self.menhir: Optional[coordinates.Coords] = None
        self.landmarks_visited: dict[coordinates.Coords, bool] = {}

        self.tiles: dict[coordinates.Coords, tiles.TileDescription] = {}
        self.last_seen: dict[coordinates.Coords, int] = {}

        # fmt:off
        self.weapons: defaultdict[coordinates.Coords, Optional[weapons.WeaponDescription]] = defaultdict(lambda: None)
        self.consumables: defaultdict[coordinates.Coords, Optional[consumables.ConsumableDescription]] = defaultdict(lambda: None)
        # fmt:on

        # Initialize
        # ----------
        if name in LANDMARKS:
            self.landmarks_visited = {landmark: False for landmark in LANDMARKS[name]}
        else:
            self.landmarks_visited = {landmark: False for landmark in self._compute_landmarks()}

        for position, tile in self._arena.terrain.items():
            self.tiles[position] = tile.description()
            self.last_seen[position] = inf

            if weapon := tile.loot:
                self.weapons[position] = weapon.description()
            if consumable := tile.consumable:
                self.consumables[position] = consumable.description()

    def update(
        self,
        position: coordinates.Coords,
        visible_tiles: dict[coordinates.Coords, tiles.TileDescription],
    ) -> None:
        self._update_menhir(visible_tiles)
        self._update_landmarks(position)
        self._update_loot(visible_tiles)
        self._remove_enemies()
        self._update_tiles(position, visible_tiles)
        self._update_last_seen(visible_tiles)

    def _update_menhir(self, visible_tiles: dict[coordinates.Coords, tiles.TileDescription]) -> None:
        if not self.menhir:
            for coords, tile in visible_tiles.items():
                coords = coordinates.Coords(*coords)
                if tile.type == "menhir":
                    self.menhir = coords

    def _update_landmarks(self, position: coordinates.Coords) -> None:
        for landmark, visited in self.landmarks_visited.copy().items():
            if not visited and self.dist(position, landmark) <= LANDMARK_RADIUS:
                self.landmarks_visited[landmark] = True
            if effects.EffectDescription("mist") in self.tiles[landmark].effects:
                del self.landmarks_visited[landmark]

        if all(self.landmarks_visited.values()) and not self.menhir:
            for landmark in self.landmarks_visited:
                self.landmarks_visited[landmark] = False

    def _update_loot(self, visible_tiles: dict[coordinates.Coords, tiles.TileDescription]) -> None:
        for coords, tile in visible_tiles.items():
            coords = coordinates.Coords(*coords)
            self.weapons[coords] = tile.loot
            self.consumables[coords] = tile.consumable

    def _update_last_seen(self, visible_tiles: dict[coordinates.Coords, tiles.TileDescription]) -> None:
        for coords in visible_tiles:
            coords = coordinates.Coords(*coords)
            self.last_seen[coords] = -1
        for coords in self.last_seen:
            coords = coordinates.Coords(*coords)
            self.last_seen[coords] += 1

    def _remove_enemies(self) -> None:
        for enemy_name, coords in self._enemy_coords.copy().items():
            if self.last_seen[coords] > ENEMY_CLEANUP_TIME:
                tile = self.tiles[coords]
                self.tiles[coords] = tiles.TileDescription(tile.type, tile.loot, None, tile.consumable, tile.effects)
                del self._enemy_coords[enemy_name]

    def _update_tiles(
        self, position: coordinates.Coords, visible_tiles: dict[coordinates.Coords, tiles.TileDescription]
    ) -> None:
        for coords, tile in visible_tiles.items():
            coords = coordinates.Coords(*coords)
            if coords == position:
                tile = tiles.TileDescription(tile.type, tile.loot, None, tile.consumable, tile.effects)

            if not tile.character and coords in self._enemy_coords.values():
                enemy_name = [e for e, pos in self._enemy_coords.items() if pos == coords][0]
                del self._enemy_coords[enemy_name]

            if enemy := tile.character:
                if (name := enemy.controller_name) in self._enemy_coords:
                    old_coords = self._enemy_coords[name]
                    old_tile = self.tiles[old_coords]
                    self.tiles[old_coords] = tiles.TileDescription(
                        old_tile.type,
                        old_tile.loot,
                        None,
                        old_tile.consumable,
                        old_tile.effects,
                    )
                self._enemy_coords[enemy.controller_name] = coords

            self.tiles[coords] = tile

    def _compute_landmarks(self, max_landmarks: int = 8) -> list[coordinates.Coords]:
        terrain = self._arena.terrain
        not_seen = set(terrain)
        landmarks = []
        for _ in range(max_landmarks):
            if len(not_seen) == 0:
                break

            best_landmark, best_visible = None, set()
            for landmark in terrain:
                if terrain[landmark].passable:
                    visible = set()
                    for facing in characters.Facing:
                        visible |= self.get_visible_coords(landmark, facing, weapons.Knife().description())

                    if len(not_seen & visible) > len(not_seen & best_visible):
                        best_landmark = landmark
                        best_visible = visible
            not_seen -= best_visible
            landmarks.append(best_landmark)
            
        return landmarks

    def get_enemies(self) -> dict[coordinates.Coords, characters.ChampionDescription]:
        return {
            coords: self.tiles[coords].character
            for coords in self._enemy_coords.values()
            if self.tiles[coords].character
        }

    def get_cut_positions(
        self,
        weapon: weapons.WeaponDescription,
        position: coordinates.Coords,
        facing: characters.Facing,
    ) -> set[coordinates.Coords]:
        weapon: weapons.Weapon = WEAPON_DICT[weapon.name]
        terrain = self._arena.terrain
        return {coords for coords in weapon.cut_positions(terrain, position, facing) if coords in terrain}

    def dist(self, s: coordinates.Coords, t: coordinates.Coords) -> int:
        h = lambda position: manhattan_dist(position, t)
        g_score = defaultdict(lambda: inf)
        f_score = defaultdict(lambda: inf)

        g_score[s] = 0
        f_score[s] = h(s)

        open_set = PriorityQueue()
        open_set.put((f_score[s], s))

        while not open_set.empty():
            score, current = open_set.get()

            if score != f_score[current]:
                continue
            if current == t:
                break

            for neighbor in self.get_adjacent(current):
                tentative_g_score = g_score[current] + 1
                if tentative_g_score < g_score[neighbor]:
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + h(neighbor)
                    open_set.put((f_score[neighbor], neighbor))

        if g_score[t] == inf and len(self.get_adjacent(t)) > 0:
            return min(g_score[neighbor] for neighbor in self.get_adjacent(t)) + 1

        return g_score[t]

    def get_min_dist_menhir(self, position: coordinates.Coords) -> int:
        if not self.menhir:
            return inf
        return self.dist(position, self.menhir)

    def get_min_dist_loot(self, position: coordinates.Coords, weapon: weapons.WeaponDescription) -> int:
        dist_weapons = inf
        for target_position, target_weapon in self.weapons.items():
            if target_weapon and WEAPON_ORDER.index(target_weapon.name) > WEAPON_ORDER.index(weapon.name):
                dist_weapons = min(dist_weapons, self.dist(position, target_position))

        dist_consumable = inf
        for target_position, target_consumable in self.consumables.items():
            if target_consumable:
                dist_consumable = min(dist_consumable, self.dist(position, target_position))

        return min(dist_weapons, dist_consumable)

    def get_min_dist_landmark(self, position: coordinates.Coords) -> int:
        if self.menhir:
            return inf

        dist_landmark = inf
        for landmark, visited in self.landmarks_visited.items():
            if not visited:
                dist_landmark = min(dist_landmark, self.dist(position, landmark))

        return dist_landmark

    def get_min_dist_prey(self, position: coordinates.Coords, health: int, weapon: weapons.WeaponDescription) -> int:
        # TODO
        dist_prey = inf
        for enemy_position, enemy in self.get_enemies().items():
            if (
                DAMAGE_DICT[weapon.name] > 0
                and DAMAGE_DICT[enemy.weapon.name] > 0
                and enemy.health / DAMAGE_DICT[weapon.name] < health / DAMAGE_DICT[enemy.weapon.name]
                and self.tiles[enemy_position].type != "forest"
            ):
                dist_prey = min(dist_prey, self.dist(position, enemy_position))

        return dist_prey

    def get_visible_coords(
        self,
        position: coordinates.Coords,
        facing: characters.Facing,
        weapon: weapons.WeaponDescription,
    ) -> set[coordinates.Coords]:
        champion = characters.Champion(position, self._arena)
        champion.facing = facing
        champion.weapon = WEAPON_DICT[weapon.name]
        return {coordinates.Coords(*position) for position in self._arena.visible_coords(champion)}

    def get_adjacent(self, position) -> set[coordinates.Coords]:
        return {
            position + facing.value
            for facing in characters.Facing
            if position + facing.value in self._arena.terrain and self.is_passable(position + facing.value)
        }

    def is_passable(self, position: coordinates.Coords) -> bool:
        return self._arena.terrain[position].passable and not self.tiles[position].character
