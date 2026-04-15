from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

from gupb.model import characters, coordinates, tiles

PASSABLE_TERRAIN = {"land", "forest", "menhir"}
TRANSPARENT_TERRAIN = {"land", "sea", "menhir"}
BLOCKING_TERRAIN = {"wall"}


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
    enemies: Dict[str, EnemyTrace] = field(default_factory=dict)
    recent_positions: deque[coordinates.Coords] = field(default_factory=lambda: deque(maxlen=14))
    idle_ticks: int = 0

    def reset(self, arena_name: str) -> None:
        self.__dict__.update(WorldState(arena_name=arena_name).__dict__)
        self.known_terrain = self._load_static_terrain(arena_name)

    def _load_static_terrain(self, arena_name: str) -> Dict[coordinates.Coords, str]:
        terrain: Dict[coordinates.Coords, str] = {}
        path = Path("resources") / "arenas" / f"{arena_name}.gupb"
        if not path.exists():
            return terrain
        weapon_spawns = {"K", "S", "A", "B", "M", "C"}
        with path.open("r", encoding="utf-8") as arena_file:
            for y, line in enumerate(arena_file.readlines()):
                for x, mark in enumerate(line.rstrip("\n")):
                    pos = coordinates.Coords(x, y)
                    if mark == "#":
                        terrain[pos] = "wall"
                    elif mark == "=":
                        terrain[pos] = "sea"
                    elif mark == "@":
                        terrain[pos] = "forest"
                    elif mark == "." or mark in weapon_spawns:
                        terrain[pos] = "land"
        return terrain

    def update_from_knowledge(self, knowledge: characters.ChampionKnowledge) -> None:
        self.turn_no += 1
        prev_position = self.position
        prev_facing = self.facing
        self.position = knowledge.position
        tile = knowledge.visible_tiles.get(knowledge.position)
        if tile and tile.character:
            self.facing = tile.character.facing
            self.health = tile.character.health
            self.weapon_name = tile.character.weapon.name
            self.loaded_bow = self.weapon_name == "bow_loaded"
        self.idle_ticks = self.idle_ticks + 1 if (self.position == prev_position and self.facing == prev_facing) else 0
        self.recent_positions.append(self.position)

        self.fire_tiles.clear()
        self.mist_tiles.clear()
        currently_seen = set(knowledge.visible_tiles.keys())

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
            if self.turn_no - self.enemies[name].seen_at > 12:
                self.enemies.pop(name)

        self.last_seen_potions = {p for p in self.last_seen_potions if p not in currently_seen or knowledge.visible_tiles[p].consumable}

    def passable(self, coords: coordinates.Coords) -> bool:
        terrain = self.known_terrain.get(coords)
        if terrain is None:
            return False
        if terrain not in PASSABLE_TERRAIN:
            return False
        tile = self.seen_tiles.get(coords)
        return not (tile and tile.character and coords != self.position)

    def transparent(self, coords: coordinates.Coords) -> bool:
        terrain = self.known_terrain.get(coords)
        if terrain is None:
            return False
        if terrain not in TRANSPARENT_TERRAIN:
            return False
        tile = self.seen_tiles.get(coords)
        return not (tile and tile.character)
