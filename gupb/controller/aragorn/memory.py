import os
from typing import Dict, NamedTuple, Optional, List

from gupb.model import arenas, tiles, coordinates, weapons, games
from gupb.model import characters, consumables, effects



class Memory:
    def __init__(self):
        self.idleTime = 0
        self.position: coordinates.Coords = None
        self.facing: characters.Facing = characters.Facing.random()
        no_of_champions_alive: int = 0
        
        self.map: Map = None
        self.environment: Environment = None
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.idleTime = 0
        self.position: coordinates.Coords = None
        self.facing: characters.Facing = characters.Facing.random()
        no_of_champions_alive: int = 0

        self.map = Map.load(arena_description.name)
        self.environment = Environment(self.map)
    
    def update(self, knowledge: characters.ChampionKnowledge) -> None:
        self.position = knowledge.position
        self.facing = knowledge.visible_tiles[self.position].character.facing
        self.no_of_champions_alive = knowledge.no_of_champions_alive
        self.visible_tiles = knowledge.visible_tiles

        for coords in knowledge.visible_tiles:
            visible_tile_description = knowledge.visible_tiles[coords]
            self.map.terrain[coords].loot = self.weaponDescriptionConverter(visible_tile_description.loot)
            self.map.terrain[coords].character = visible_tile_description.character
            self.map.terrain[coords].consumable = self.consumableDescriptionConverter(visible_tile_description.consumable)
            self.map.terrain[coords].effects = self.effectsDescriptionConverter(visible_tile_description.effects)
        
        self.idleTime += 1
        # TODO: check if environment_action is called before turn or after
        self.environment.environment_action(self.no_of_champions_alive)
    
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
    
    def hasOponentInFront(self):
        frontCell = coordinates.add_coords(self.position, self.facing.value)
        
        if frontCell in self.map.terrain and self.map.terrain[frontCell].character is not None:
            return True
        
        return False
    
    def resetIdle(self):
        self.idleTime = 0

    def willGetIdlePenalty(self):
        return self.idleTime > characters.PENALISED_IDLE_TIME - 1

class Environment:
    def __init__(self, map: 'Map'):
        self.episode = 0
        self.episodes_since_mist_increase = 0
        self.map = map

    def environment_action(self, no_of_champions_alive) -> None:
        self.episode += 1
        self.episodes_since_mist_increase += 1

        if self.episodes_since_mist_increase >= games.MIST_TTH_PER_CHAMPION * no_of_champions_alive:
            self.map.increase_mist()
            self.episodes_since_mist_increase = 0
class Map:
    def __init__(self, name: str, terrain: arenas.Terrain) -> None:
        self.name = name
        self.terrain: arenas.Terrain = terrain
        self.size: tuple[int, int] = arenas.terrain_size(self.terrain)
        self.menhir_position: Optional[coordinates.Coords] = None
        self.mist_radius = int(self.size[0] * 2 ** 0.5) + 1
        self.passableCenter = self.__getPassableCenter()
        self.hidingSpot = self.__getHidingSpot()

    @staticmethod
    def load(name: str) -> 'Map':
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
        return Map(name, terrain)
    
    def increase_mist(self) -> None:
        self.mist_radius -= 1 if self.mist_radius > 0 else self.mist_radius
    
    def __getPassableCenter(self) -> coordinates.Coords|None:
        mapSize = self.size
        
        for r in range(mapSize[0] // 2):
            for x in range(mapSize[0] // 2 - r, mapSize[0] // 2 + r + 1):
                for y in range(mapSize[1] // 2 - r, mapSize[1] // 2 + r + 1):
                    coordToCheck = coordinates.Coords(x, y)

                    if coordToCheck in self.terrain and self.terrain[coordToCheck].terrain_passable():
                        return coordToCheck
        
        return None
    
    def __getHidingSpot(self) -> [coordinates.Coords|None,characters.Facing]:
        if self.name == 'ordinary_chaos':
            return coordinates.Coords(4, 9), characters.Facing.DOWN
        
        return None, None
    
    def getWeaponPos(self, weponType: weapons.Weapon):
        if weponType == weapons.Sword:
            return coordinates.Coords(4, 14)

        return None
