from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Dict

from gupb.model import arenas, characters, coordinates, tiles

PASSABLE_TERRAIN = {"land", "forest", "menhir"}
TRANSPARENT_TERRAIN = {"land", "sea", "menhir"}
BLOCKING_TERRAIN = {"wall"}
WEAPON_SPAWNS = {
    "K": "knife",
    "S": "sword",
    "A": "axe",
    "B": "bow_unloaded",
    "M": "amulet",
    "C": "scroll",
}
ENEMY_MEMORY_TURNS = 5


@dataclass
class EnemyTrace:
    position: coordinates.Coords
    facing: characters.Facing
    weapon_name: str
    health: int
    seen_at: int


@dataclass
class WorldState:
    arena_name: str = ""
    turn_no: int = 0
    position: coordinates.Coords = coordinates.Coords(0, 0)
    facing: characters.Facing = characters.Facing.UP
    health: int = 8
    weapon_name: str = "knife"
    loaded_bow: bool = False
    known_terrain: Dict[coordinates.Coords, str] = field(default_factory=dict)
    seen_tiles: Dict[coordinates.Coords, tiles.TileDescription] = field(default_factory=dict)
    last_seen_loot: Dict[coordinates.Coords, str] = field(default_factory=dict)
    last_seen_potions: set[coordinates.Coords] = field(default_factory=set)
    fire_tiles: set[coordinates.Coords] = field(default_factory=set)
    mist_tiles: set[coordinates.Coords] = field(default_factory=set)
    menhir_position: coordinates.Coords | None = None
    arena_size: tuple[int, int] | None = None
    estimated_mist_radius: int | None = None
    mist_tick_counter: int = 0
    alive_count: int = 1
    scroll_charges: int = 0
    enemies: Dict[str, EnemyTrace] = field(default_factory=dict)
    recent_positions: deque[coordinates.Coords] = field(default_factory=lambda: deque(maxlen=14))
    idle_ticks: int = 0

    def reset(self, arena_name: str) -> None:
        self.__dict__.update(WorldState(arena_name=arena_name).__dict__)
        self.known_terrain, self.last_seen_loot, self.arena_size = self._load_static_map(arena_name)
        if self.arena_size:
            self.estimated_mist_radius = int(self.arena_size[0] * math.sqrt(2)) + 1
        self.menhir_position = arenas.FIXED_MENHIRS.get(arena_name)

    def _load_static_map(
        self,
        arena_name: str,
    ) -> tuple[Dict[coordinates.Coords, str], Dict[coordinates.Coords, str], tuple[int, int] | None]:
        terrain: Dict[coordinates.Coords, str] = {}
        loot: Dict[coordinates.Coords, str] = {}
        path = Path("resources") / "arenas" / f"{arena_name}.gupb"
        if not path.exists():
            return terrain, loot, None
        width = 0
        height = 0
        with path.open("r", encoding="utf-8") as arena_file:
            for y, line in enumerate(arena_file.readlines()):
                row = line.rstrip("\n")
                width = max(width, len(row))
                height = y + 1
                for x, mark in enumerate(row):
                    pos = coordinates.Coords(x, y)
                    if mark == "#":
                        terrain[pos] = "wall"
                    elif mark == "=":
                        terrain[pos] = "sea"
                    elif mark == "@":
                        terrain[pos] = "forest"
                    elif mark == "." or mark in WEAPON_SPAWNS:
                        terrain[pos] = "land"
                        if mark in WEAPON_SPAWNS:
                            loot[pos] = WEAPON_SPAWNS[mark]
        return terrain, loot, (width, height)

    def update_from_knowledge(self, knowledge: characters.ChampionKnowledge) -> None:
        self.turn_no += 1
        self.alive_count = knowledge.no_of_champions_alive
        prev_position = self.position
        prev_facing = self.facing
        prev_weapon = self.weapon_name
        self.position = knowledge.position
        tile = knowledge.visible_tiles.get(knowledge.position)
        if tile and tile.character:
            self.facing = tile.character.facing
            self.health = tile.character.health
            self.weapon_name = tile.character.weapon.name
            self.loaded_bow = self.weapon_name == "bow_loaded"
            if self.weapon_name == "scroll" and prev_weapon != "scroll":
                self.scroll_charges = 5
            elif self.weapon_name != "scroll":
                self.scroll_charges = 0
        self.idle_ticks = self.idle_ticks + 1 if (self.position == prev_position and self.facing == prev_facing) else 0
        self.recent_positions.append(self.position)

        currently_seen = set(knowledge.visible_tiles.keys())
        visible_enemy_names: set[str] = set()

        for coords, desc in knowledge.visible_tiles.items():
            self.seen_tiles[coords] = desc
            self.known_terrain[coords] = desc.type
            if desc.type == "menhir":
                self.menhir_position = coords
            if desc.loot:
                self.last_seen_loot[coords] = desc.loot.name
            elif coords in self.last_seen_loot:
                self.last_seen_loot.pop(coords)
            if desc.consumable and desc.consumable.name == "potion":
                self.last_seen_potions.add(coords)
            elif coords in self.last_seen_potions:
                self.last_seen_potions.remove(coords)

            enemy = desc.character
            if enemy and enemy.controller_name != "" and coords != self.position:
                visible_enemy_names.add(enemy.controller_name)
                self.enemies[enemy.controller_name] = EnemyTrace(
                    position=coords,
                    facing=enemy.facing,
                    weapon_name=enemy.weapon.name,
                    health=enemy.health,
                    seen_at=self.turn_no,
                )

            for effect in desc.effects:
                if effect.type == "fire":
                    self.fire_tiles.add(coords)
                elif effect.type == "mist":
                    self.mist_tiles.add(coords)

        for name in list(self.enemies.keys()):
            enemy = self.enemies[name]
            if name not in visible_enemy_names and enemy.position in currently_seen:
                self.enemies.pop(name)
            elif self.turn_no - enemy.seen_at > ENEMY_MEMORY_TURNS:
                self.enemies.pop(name)

        self._advance_mist(knowledge.no_of_champions_alive)
        self.last_seen_potions = {p for p in self.last_seen_potions if p not in currently_seen or knowledge.visible_tiles[p].consumable}

    def _advance_mist(self, alive_count: int) -> None:
        if self.estimated_mist_radius is None and self.arena_size:
            self.estimated_mist_radius = int(self.arena_size[0] * math.sqrt(2)) + 1
        if self.menhir_position is not None:
            observed = [
                int(math.sqrt((coords.x - self.menhir_position.x) ** 2 + (coords.y - self.menhir_position.y) ** 2))
                for coords in self.mist_tiles
            ]
            if observed:
                observed_radius = min(observed)
                if self.estimated_mist_radius is None or observed_radius < self.estimated_mist_radius:
                    self.estimated_mist_radius = observed_radius
                    self.mist_tick_counter = 0
                    return

        self.mist_tick_counter += 1
        threshold = 2 * max(alive_count, 1)
        if self.estimated_mist_radius is not None and self.mist_tick_counter >= threshold:
            self.estimated_mist_radius = max(0, self.estimated_mist_radius - 1)
            self.mist_tick_counter = 0

    def passable(self, coords: coordinates.Coords) -> bool:
        terrain = self.known_terrain.get(coords)
        if terrain is None:
            return False
        if terrain not in PASSABLE_TERRAIN:
            return False
        return not self.occupied(coords)

    def transparent(self, coords: coordinates.Coords) -> bool:
        terrain = self.known_terrain.get(coords)
        if terrain is None:
            return False
        if terrain not in TRANSPARENT_TERRAIN:
            return False
        return not self.occupied(coords)

    def occupied(self, coords: coordinates.Coords) -> bool:
        return any(
            enemy.position == coords and self.turn_no - enemy.seen_at <= ENEMY_MEMORY_TURNS
            for enemy in self.enemies.values()
        )

    def predicted_mist(self, coords: coordinates.Coords, ticks_ahead: int = 0) -> bool:
        if coords in self.mist_tiles:
            return True
        if self.menhir_position is None or self.estimated_mist_radius is None:
            return False
        threshold = 2 * max(1, self.alive_count)
        radius = max(0, self.estimated_mist_radius - ((self.mist_tick_counter + ticks_ahead) // threshold))
        if radius <= 0:
            return coords != self.menhir_position
        dx = coords.x - self.menhir_position.x
        dy = coords.y - self.menhir_position.y
        return dx * dx + dy * dy >= radius * radius

    def nearest_mist_distance(self, coords: coordinates.Coords | None = None) -> int | None:
        if not self.mist_tiles:
            return None
        origin = coords or self.position
        return min(abs(origin.x - mist.x) + abs(origin.y - mist.y) for mist in self.mist_tiles)
