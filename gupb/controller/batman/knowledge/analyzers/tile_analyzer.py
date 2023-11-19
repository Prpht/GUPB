from typing import Optional
from functools import cached_property

from gupb.model.coordinates import Coords
from gupb.model.characters import Facing
from gupb.controller.batman.knowledge.knowledge import (
    Knowledge,
    ArenaKnowledge,
    TileKnowledge,
)


class TileAnalyzer:
    def __init__(self, knowledge: Knowledge, position: Coords):
        self.knowledge = knowledge
        self.arena = knowledge.arena
        self.position = position
        self.tile_knowledge = self.arena.explored_map.get(
            position, TileKnowledge(position)
        )

    @cached_property
    def is_out_of_map(self):
        # TODO assuming knowledge.arena.area_size is the real size of the arena
        return (
            self.position.x < 0
            or self.position.y < 0
            or self.position.x >= self.arena.arena_size[0]
            or self.position.y >= self.arena.arena_size[1]
        )

    # tile properties
    @cached_property
    def tile_type(self) -> str:
        return self.tile_knowledge.type

    @property
    def is_wall(self) -> bool:
        return self.tile_type == "wall"

    @property
    def is_water(self) -> bool:
        return self.tile_type == "water"

    @property
    def is_menhir(self) -> bool:
        return self.tile_type == "menhir"

    @property
    def is_attacked(self) -> bool:
        return self.tile_knowledge.attacked

    @property
    def has_mist(self) -> bool:
        return self.tile_knowledge.mist

    @property
    def last_seen(self) -> int:
        return self.tile_knowledge.last_seen

    # weapons
    @cached_property
    def weapon(self) -> str:
        return (
            self.tile_knowledge.weapon.name
            if self.tile_knowledge.weapon is not None
            else "none"
        )

    @property
    def has_knife(self) -> bool:
        return self.weapon == "knife"

    @property
    def has_sword(self) -> bool:
        return self.weapon == "sword"

    @property
    def has_bow(self) -> bool:
        return self.weapon == "bow"

    @property
    def has_axe(self) -> bool:
        return self.weapon == "axe"

    @property
    def has_amulet(self) -> bool:
        return self.weapon == "amulet"

    # characters
    @property
    def has_enemy(self) -> bool:
        return (
            self.tile_knowledge.character is not None
            and self.position != self.knowledge.position
        )

    @property
    def character_health(self) -> int:
        character = self.tile_knowledge.character
        return character.health if character is not None else 0

    @cached_property
    def character_weapon(self) -> str:
        character = self.tile_knowledge.character
        return character.weapon.name if character is not None else "none"

    @property
    def has_character_with_knife(self) -> bool:
        return self.character_weapon == "knife"

    @property
    def has_character_with_sword(self) -> bool:
        return self.character_weapon == "sword"

    @property
    def has_character_with_bow(self) -> bool:
        return self.character_weapon == "bow"

    @property
    def has_character_with_axe(self) -> bool:
        return self.character_weapon == "axe"

    @property
    def has_character_with_amulet(self) -> bool:
        return self.character_weapon == "amulet"

    @cached_property
    def character_facing(self) -> Optional[Facing]:
        character = self.tile_knowledge.character
        return character.facing if character is not None else None

    @property
    def has_character_facing_up(self) -> bool:
        return self.character_facing == Facing.UP

    @property
    def has_character_facing_down(self) -> bool:
        return self.character_facing == Facing.DOWN

    @property
    def has_character_facing_left(self) -> bool:
        return self.character_facing == Facing.LEFT

    @property
    def has_character_facing_right(self) -> bool:
        return self.character_facing == Facing.RIGHT

    # consumables
    @cached_property
    def consumable(self) -> str:
        return (
            self.tile_knowledge.consumable.name
            if self.tile_knowledge.consumable is not None
            else "none"
        )

    @property
    def has_potion(self) -> bool:
        return self.consumable == "potion"
