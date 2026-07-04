from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

from .utils import PASSABLE_TILE_TYPES, TRANSPARENT_TILE_TYPES, to_coords


@dataclass(slots=True)
class EnemyMemory:
    position: coordinates.Coords
    description: characters.ChampionDescription
    turn_seen: int


@dataclass(slots=True)
class WorldMemory:
    known_tile_type: dict[coordinates.Coords, str] = field(default_factory=dict)
    known_loot: dict[coordinates.Coords, str] = field(default_factory=dict)
    known_consumables: dict[coordinates.Coords, str] = field(default_factory=dict)
    known_mist_positions: set[coordinates.Coords] = field(default_factory=set)
    known_fire_positions: set[coordinates.Coords] = field(default_factory=set)
    last_seen_enemies: dict[str, EnemyMemory] = field(default_factory=dict)
    recent_positions: deque[coordinates.Coords] = field(default_factory=lambda: deque(maxlen=16))
    menhir_position: coordinates.Coords | None = None
    arena_name: str | None = None
    map_preloaded: bool = False
    turn_no: int = 0
    last_health: int | None = None

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.known_tile_type.clear()
        self.known_loot.clear()
        self.known_consumables.clear()
        self.known_mist_positions.clear()
        self.known_fire_positions.clear()
        self.last_seen_enemies.clear()
        self.recent_positions.clear()
        self.menhir_position = None
        self.arena_name = arena_description.name
        self.map_preloaded = False
        self.turn_no = 0
        self.last_health = None
        self._preload_arena(arena_description.name)

    def _preload_arena(self, arena_name: str) -> None:
        try:
            arena = arenas.Arena.load(arena_name)
        except Exception:
            return

        for coords_, tile in arena.terrain.items():
            self.known_tile_type[to_coords(coords_)] = tile.__class__.__name__.lower()
            if tile.loot is not None:
                self.known_loot[to_coords(coords_)] = tile.loot.description().name
        self.map_preloaded = True

    def update(self, knowledge: characters.ChampionKnowledge, own_name: str) -> None:
        self.turn_no += 1
        self.recent_positions.append(to_coords(knowledge.position))
        visible_enemy_names: set[str] = set()

        for raw_coords, tile in knowledge.visible_tiles.items():
            coords_ = to_coords(raw_coords)
            self.known_tile_type[coords_] = tile.type

            if tile.loot is None:
                self.known_loot.pop(coords_, None)
            else:
                self.known_loot[coords_] = tile.loot.name

            if tile.consumable is None:
                self.known_consumables.pop(coords_, None)
            else:
                self.known_consumables[coords_] = tile.consumable.name

            effect_names = {effect.type for effect in tile.effects}
            if "mist" in effect_names:
                self.known_mist_positions.add(coords_)
            else:
                self.known_mist_positions.discard(coords_)
            if "fire" in effect_names:
                self.known_fire_positions.add(coords_)
            else:
                self.known_fire_positions.discard(coords_)

            if tile.type == "menhir":
                self.menhir_position = coords_

            if tile.character is not None and coords_ != knowledge.position:
                if tile.character.controller_name != own_name:
                    visible_enemy_names.add(tile.character.controller_name)
                    self.last_seen_enemies[tile.character.controller_name] = EnemyMemory(
                        position=coords_,
                        description=tile.character,
                        turn_seen=self.turn_no,
                    )

        stale_names = [
            name
            for name, enemy in self.last_seen_enemies.items()
            if name not in visible_enemy_names and self.turn_no - enemy.turn_seen > 12
        ]
        for name in stale_names:
            self.last_seen_enemies.pop(name, None)

    def tile_type_at(self, coords_: coordinates.Coords) -> str | None:
        return self.known_tile_type.get(to_coords(coords_))

    def character_at(self, coords_: coordinates.Coords, knowledge: characters.ChampionKnowledge):
        tile = knowledge.visible_tiles.get(to_coords(coords_))
        if tile is None:
            return None
        return tile.character

    def is_known_passable(self, coords_: coordinates.Coords) -> bool:
        return self.tile_type_at(coords_) in PASSABLE_TILE_TYPES

    def is_transparent(self, coords_: coordinates.Coords) -> bool:
        return self.tile_type_at(coords_) in TRANSPARENT_TILE_TYPES

    def self_description(
        self,
        knowledge: characters.ChampionKnowledge,
    ) -> characters.ChampionDescription | None:
        own_tile = knowledge.visible_tiles.get(to_coords(knowledge.position))
        if own_tile is None:
            return None
        return own_tile.character

    def visible_enemies(
        self,
        knowledge: characters.ChampionKnowledge,
        own_name: str,
    ) -> list[tuple[coordinates.Coords, characters.ChampionDescription]]:
        enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]] = []
        for raw_coords, tile in knowledge.visible_tiles.items():
            coords_ = to_coords(raw_coords)
            if coords_ == knowledge.position or tile.character is None:
                continue
            if tile.character.controller_name == own_name:
                continue
            enemies.append((coords_, tile.character))
        enemies.sort(key=lambda pair: abs(pair[0].x - knowledge.position.x) + abs(pair[0].y - knowledge.position.y))
        return enemies

    def visible_mist_positions(self, knowledge: characters.ChampionKnowledge) -> list[coordinates.Coords]:
        positions: set[coordinates.Coords] = set(self.known_mist_positions)
        for raw_coords, tile in knowledge.visible_tiles.items():
            if any(effect.type == "mist" for effect in tile.effects):
                positions.add(to_coords(raw_coords))
        return list(positions)

    def visible_fire_positions(self, knowledge: characters.ChampionKnowledge) -> list[coordinates.Coords]:
        positions: set[coordinates.Coords] = set(self.known_fire_positions)
        for raw_coords, tile in knowledge.visible_tiles.items():
            if any(effect.type == "fire" for effect in tile.effects):
                positions.add(to_coords(raw_coords))
        return list(positions)

    def frontier_targets(self) -> set[coordinates.Coords]:
        if self.map_preloaded:
            passable = {
                coords_
                for coords_, tile_type in self.known_tile_type.items()
                if tile_type in PASSABLE_TILE_TYPES
            }
            unrecent = passable - set(self.recent_positions)
            return unrecent or passable

        targets: set[coordinates.Coords] = set()
        for coords_, tile_type in self.known_tile_type.items():
            if tile_type not in PASSABLE_TILE_TYPES:
                continue
            for delta in (
                coordinates.Coords(0, -1),
                coordinates.Coords(1, 0),
                coordinates.Coords(0, 1),
                coordinates.Coords(-1, 0),
            ):
                neighbor = coords_ + delta
                if neighbor not in self.known_tile_type:
                    targets.add(coords_)
                    break
        return targets
