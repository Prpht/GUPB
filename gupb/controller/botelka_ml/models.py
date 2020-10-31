from dataclasses import dataclass
from enum import Enum
from typing import Optional

from gupb.model.arenas import Arena
from gupb.model.characters import ChampionKnowledge, Facing
from gupb.model.coordinates import Coords, add_coords
from gupb.model.weapons import Weapon, Axe, Sword, Amulet, Knife, Bow

WEAPONS = {
    "bow": Bow(),
    "axe": Axe(),
    "sword": Sword(),
    "knife": Knife(),
    "amulet": Amulet(),
}


def weapon_ranking(weapon: Weapon) -> int:
    if isinstance(weapon, Bow):
        return 10
    if isinstance(weapon, Amulet):
        return 8
    if isinstance(weapon, Axe):
        return 6
    if isinstance(weapon, Sword):
        return 6
    return 0


class DistanceMeasure(Enum):
    CLOSE = 0
    FAR = 1
    VERY_FAR = 2
    INACCESSIBLE = 3


@dataclass
class Wisdom:
    arena: Arena
    knowledge: Optional[ChampionKnowledge]
    bot_name: str
    prev_knowledge: Optional[ChampionKnowledge] = None

    def next_knowledge(self, knowledge:ChampionKnowledge):
        self.prev_knowledge = self.knowledge
        self.knowledge = knowledge

    @property
    def coords_did_not_change(self):
        if not self.prev_knowledge:
            return False
        return self.knowledge.position == self.prev_knowledge.position

    @property
    def bot_coords(self) -> Coords:
        return self.knowledge.position

    @property
    def bot_facing(self) -> Facing:
        tile = self.knowledge.visible_tiles[self.bot_coords]

        assert tile.character, "Character must be standing on a tile"

        return tile.character.facing

    @property
    def bot_health(self) -> int:
        tile = self.knowledge.visible_tiles[self.bot_coords]

        assert tile.character, "Character must be standing on a tile"

        return tile.character.health

    @property
    def bot_weapon(self) -> Weapon:
        tile = self.knowledge.visible_tiles[self.bot_coords]

        assert tile.character, "Character must be standing on a tile"

        weapon_name = tile.character.weapon.name

        return WEAPONS[weapon_name]

    @property
    def mist_visible(self) -> bool:
        return any(
            visible_tile
            for visible_tile in self.knowledge.visible_tiles.values()
            if "mist" in {effect.type for effect in visible_tile.effects}
        )

    @property
    def enemies_visible(self) -> bool:
        return any(
            visible_tile
            for visible_tile in self.knowledge.visible_tiles.values()
            if visible_tile.character
        )

    @property
    def better_weapon_visible(self) -> bool:
        return any(
            tile
            for tile in self.knowledge.visible_tiles.values()
            if tile.loot and weapon_ranking(WEAPONS.get(tile.loot.name)) > weapon_ranking(self.bot_weapon)
        )

    @property
    def will_pick_up_worse_weapon(self) -> bool:
        coords_in_front = add_coords(self.bot_coords, self.bot_facing.value)

        if not self.knowledge.visible_tiles[coords_in_front].loot:
            return False

        weapon_in_front = WEAPONS.get(self.knowledge.visible_tiles[coords_in_front].loot.name)

        return weapon_ranking(weapon_in_front) < weapon_ranking(self.bot_weapon)

    @property
    def can_attack_player(self) -> bool:
        return any(
            coord
            for coord in self.bot_weapon.cut_positions(self.arena.terrain, self.bot_coords, self.bot_facing)
            if self.knowledge.visible_tiles[coord].character
        )

    @property
    def distance_to_menhir(self) -> int:
        # @TODO
        return DistanceMeasure.VERY_FAR.value
