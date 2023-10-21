import os
from typing import Dict, NamedTuple, Optional, List

from gupb.model import arenas, tiles, coordinates, weapons
from gupb.model import characters, consumables, effects



class Memory:
    def __init__(self):
        self.position: coordinates.Coords = None
        no_of_champions_alive: int = 0
        self.map: Map = None
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.position: coordinates.Coords = None
        no_of_champions_alive: int = 0
        self.map = Map.load(arena_description.name)
    
    def update(self, knowledge: characters.ChampionKnowledge) -> None:
        self.position = knowledge.position
        self.no_of_champions_alive = knowledge.no_of_champions_alive

        for coords in knowledge.visible_tiles:
            visible_tile_description = knowledge.visible_tiles[coords]
            self.map.terrain[coords].loot = self.weaponDescriptionConverter(visible_tile_description.loot)
            self.map.terrain[coords].character = visible_tile_description.character
            self.map.terrain[coords].consumable = self.consumableDescriptionConverter(visible_tile_description.consumable)
            self.map.terrain[coords].effects = self.effectsDescriptionConverter(visible_tile_description.effects)
    
    def weaponDescriptionConverter(self, weaponName: str) -> weapons.Weapon:
        if weaponName == 'knife':
            return weapons.Knife
        elif weaponName == 'sword':
            return weapons.Sword
        elif weaponName == 'axe':
            return weapons.Axe
        elif weaponName == 'bow':
            return weapons.Bow
        elif weaponName == 'amulet':
            return weapons.Amulet
        else:
            return None
    
    def consumableDescriptionConverter(self, consumableName: str) -> consumables.Consumable:
        if consumableName == 'potion':
            return consumables.Potion
        return None
    
    def effectsDescriptionConverter(self, effects: List[effects.EffectDescription]) -> list[effects.Effect]:
        convertedEffects = []

        for effect in effects:
            if effect == 'mist':
                convertedEffects.append(effects.Mist)
            # we dont need to know weapon cuts
            # elif effect == 'weaponcut':
            #     convertedEffects.append(effects.WeaponCut)
        
        return convertedEffects

class Map:
    def __init__(self, name: str, terrain: arenas.Terrain) -> None:
        self.name = name
        self.terrain: arenas.Terrain = terrain
        self.size: tuple[int, int] = arenas.terrain_size(self.terrain)
        self.menhir_position: Optional[coordinates.Coords] = None
        self.mist_radius = int(self.size[0] * 2 ** 0.5) + 1

    @staticmethod
    def load(name: str) -> arenas.Arena:
        terrain = dict()
        arena_file_path = os.path.join('resources', 'arenas', f'{name}.gupb')
        with open(arena_file_path) as file:
            for y, line in enumerate(file.readlines()):
                for x, character in enumerate(line):
                    if character != '\n':
                        position = coordinates.Coords(x, y)
                        if character in arenas.TILE_ENCODING:
                            terrain[position] = arenas.TILE_ENCODING[character]()
                        elif character in arenas.WEAPON_ENCODING:
                            terrain[position] = tiles.Land()
                            terrain[position].loot = arenas.WEAPON_ENCODING[character]()
        return arenas.Arena(name, terrain)
