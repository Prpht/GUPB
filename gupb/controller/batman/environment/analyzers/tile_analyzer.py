from typing import Optional
from functools import cached_property

from gupb.model.coordinates import Coords
from gupb.model.characters import Facing
from gupb.controller.batman.environment.knowledge import Knowledge, ArenaKnowledge, TileKnowledge


class TileAnalyzer:
    def __init__(self, knowledge: Knowledge, position: Coords):
        self.knowledge = knowledge
        self.arena = knowledge.arena
        self.position = position
        self.tile_knowledge = self.arena.explored_map.get(position, TileKnowledge(position))

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

    def is_wall(self) -> bool:
        return self.tile_type == "wall"

    def is_water(self) -> bool:
        return self.tile_type == "water"

    def is_manhir(self) -> bool:
        return self.tile_type == "manhir"

    def is_attacked(self) -> bool:
        return self.tile_knowledge.attacked

    def has_mist(self) -> bool:
        return self.tile_knowledge.mist

    def last_seen(self) -> int:
        return self.tile_knowledge.last_seen

    # weapons
    @cached_property
    def weapon(self) -> str:
        return self.tile_knowledge.weapon.name if self.tile_knowledge.weapon is not None else "none"

    def has_knife(self) -> bool:
        return self.weapon == "knife"

    def has_sword(self) -> bool:
        return self.weapon == "sword"

    def has_bow(self) -> bool:
        return self.weapon == "bow"

    def has_axe(self) -> bool:
        return self.weapon == "axe"

    def has_amulet(self) -> bool:
        return self.weapon == "amulet"

    # characters
    def has_enemy(self) -> bool:
        return self.tile_knowledge.character is not None \
            and self.position != self.knowledge.position

    def character_health(self) -> int:
        character = self.tile_knowledge.character
        return character.health if character is not None else 0

    @cached_property
    def character_weapon(self) -> str:
        character = self.tile_knowledge.character
        return character.weapon.name if character is not None else "none"

    def has_character_with_knife(self) -> bool:
        return self.character_weapon == "knife"

    def has_character_with_sword(self) -> bool:
        return self.character_weapon == "sword"

    def has_character_with_bow(self) -> bool:
        return self.character_weapon == "bow"

    def has_character_with_axe(self) -> bool:
        return self.character_weapon == "axe"

    def has_character_with_amulet(self) -> bool:
        return self.character_weapon == "amulet"

    @cached_property
    def character_facing(self) -> Optional[Facing]:
        character = self.tile_knowledge.character
        return character.facing if character is not None else None

    def has_character_facing_up(self) -> bool:
        return self.character_facing == Facing.UP

    def has_character_facing_down(self) -> bool:
        return self.character_facing == Facing.DOWN

    def has_character_facing_left(self) -> bool:
        return self.character_facing == Facing.LEFT

    def has_character_facing_right(self) -> bool:
        return self.character_facing == Facing.RIGHT

    # consumables
    @cached_property
    def consumable(self) -> str:
        return self.tile_knowledge.consumable.name if self.tile_knowledge.consumable is not None else "none"

    def has_potion(self) -> bool:
        return self.consumable == "potion"
