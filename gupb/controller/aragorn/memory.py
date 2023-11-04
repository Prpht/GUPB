import os
from typing import Dict, NamedTuple, Optional, List

from gupb.model import arenas, tiles, coordinates, weapons, games
from gupb.model import characters, consumables, effects
from gupb.model.characters import CHAMPION_STARTING_HP

from gupb.controller.aragorn import utils
from gupb.controller.aragorn.constants import DEBUG, INFINITY




class Memory:
    def __init__(self):
        self.tick = 0

        self.idleTime = 0
        self.position: coordinates.Coords = None
        self.facing: characters.Facing = characters.Facing.random()
        self.no_of_champions_alive: int = 0
        
        self.map: Map = None
        self.environment: Environment = None

        self.health: int = 0
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.tick = 0

        self.idleTime = 0
        self.position: coordinates.Coords = None
        self.facing: characters.Facing = characters.Facing.random()
        self.no_of_champions_alive: int = 0

        self.map = Map.loadRandom('random', coordinates.Coords(24, 24))
        self.environment = Environment(self.map)

        self.health: int = 0
    
    def update(self, knowledge: characters.ChampionKnowledge) -> None:
        self.tick += 1

        self.position = knowledge.position
        self.facing = knowledge.visible_tiles[self.position].character.facing
        self.no_of_champions_alive = knowledge.no_of_champions_alive

        self.map.parseVisibleTiles(knowledge.visible_tiles, self.tick)
        
        self.idleTime += 1
        self.environment.environment_action(self.no_of_champions_alive)

        self.health = knowledge.visible_tiles[self.position].character.health

    def hasOponentInFront(self):
        frontCell = coordinates.add_coords(self.position, self.facing.value)
        
        if frontCell in self.map.terrain and self.map.terrain[frontCell].character is not None:
            return True
        
        return False

    def hasOponentOnRight(self):
        rightCell = coordinates.add_coords(self.position, self.facing.turn_right().value)

        if rightCell in self.map.terrain and self.map.terrain[rightCell].character is not None:
            return True

        return False

    def hasOponentOnLeft(self):
        leftCell = coordinates.add_coords(self.position, self.facing.turn_left().value)

        if leftCell in self.map.terrain and self.map.terrain[leftCell].character is not None:
            return True

        return False


    def resetIdle(self):
        self.idleTime = 0

    def willGetIdlePenalty(self):
        return self.idleTime > characters.PENALISED_IDLE_TIME - 1
    
    def getDistanceToClosestPotion(self):
        minDistance = INFINITY
        minCoords = None

        for coords in self.map.terrain:
            if self.map.terrain[coords].consumable == consumables.Potion:
                distance = utils.coordinatesDistance(self.position, coords)

                if distance < minDistance:
                    minDistance = distance
                    minCoords = coords
        
        return [minDistance, minCoords]

    def getDistanceToClosestWeapon(self):
        minDistance = INFINITY
        minCoords = None

        for coords in self.map.terrain:
            if self.map.terrain[coords].loot == weapons.Weapon:
                distance = utils.coordinatesDistance(self.position, coords)

                if distance < minDistance:
                    minDistance = distance
                    minCoords = coords
        return [minDistance, minCoords]

    def isWeak(self):
        if self.health < 0.5 * CHAMPION_STARTING_HP:
            return True

        return False



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

        self.menhirCalculator = MenhirCalculator(self)

    @staticmethod
    def load(name: str) -> 'Map':
        terrain = dict()

        # predefined map
        # (not used anymore)
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
    
    @staticmethod
    def loadRandom(name: str = 'generated', size: coordinates.Coords = None) -> 'Map':
        terrain = dict()

        # load empty map
        # if size is given - assume everything a land
        if size is not None:
            for y in range(size[1]):
                for x in range(size[0]):
                    position = coordinates.Coords(x, y)
                    terrain[position] = tiles.Land()
        
        return Map(name, terrain)
    
    def parseVisibleTiles(self, visibleTiles: Dict[coordinates.Coords, tiles.Tile], currentTick :int) -> None:
        for coords in visibleTiles:
            visible_tile_description = visibleTiles[coords]
            
            if not coords in self.terrain:
                self.terrain[coords] = tiles.Land()
            
            if self.terrain[coords].__class__.__name__.lower() != visible_tile_description.type:
                newType = None

                if visible_tile_description.type == 'land':
                    newType = tiles.Land
                elif visible_tile_description.type == 'sea':
                    newType = tiles.Sea
                elif visible_tile_description.type == 'wall':
                    newType = tiles.Wall
                elif visible_tile_description.type == 'menhir':
                    newType = tiles.Menhir

                    if isinstance(coords, coordinates.Coords):
                        coordsWithCorrectType = coords
                    elif isinstance(coords, tuple):
                        coordsWithCorrectType = coordinates.Coords(coords[0], coords[1])
                    else:
                        coordsWithCorrectType = coords
                        if DEBUG:
                            print("[Map] Trying to set menhir pos to non Coords object (" + str(coords) + " of type " + str(type(coords)) + ")")
                    
                    self.menhir_position = coordsWithCorrectType
                    self.menhirCalculator.setMenhirPos(coordsWithCorrectType)
                else:
                    newType = tiles.Land
                
                self.terrain[coords] = newType()
            
            self.terrain[coords].tick = currentTick
            self.terrain[coords].loot = self.weaponDescriptionConverter(visible_tile_description.loot)
            self.terrain[coords].character = visible_tile_description.character
            self.terrain[coords].consumable = self.consumableDescriptionConverter(visible_tile_description.consumable)
            
            tileEffects = self.effectsDescriptionConverter(visible_tile_description.effects)
            self.terrain[coords].effects = tileEffects

            if effects.Mist in tileEffects:
                self.menhirCalculator.addMist(coords)
    
    def weaponDescriptionConverter(self, weaponDescription: weapons.WeaponDescription) -> weapons.Weapon:
        if weaponDescription is None or not isinstance(weaponDescription, weapons.WeaponDescription):
            return None
        
        if weaponDescription.name == 'knife':
            return weapons.Knife
        elif weaponDescription.name == 'sword':
            return weapons.Sword
        elif weaponDescription.name == 'axe':
            return weapons.Axe
        elif weaponDescription.name == 'bow':
            return weapons.Bow
        elif weaponDescription.name == 'amulet':
            return weapons.Amulet
        else:
            return None
    
    def consumableDescriptionConverter(self, consumableDescription: consumables.ConsumableDescription) -> consumables.Consumable:
        if consumableDescription is None or not isinstance(consumableDescription, consumables.ConsumableDescription):
            return None
        
        if consumableDescription.name == 'potion':
            return consumables.Potion
        return None
    
    def effectsDescriptionConverter(self, effectsToConvert: List[effects.EffectDescription]) -> list[effects.Effect]:
        convertedEffects = []

        for effect in effectsToConvert:
            if effect.type == 'mist':
                convertedEffects.append(effects.Mist)
            # we dont need to know weapon cuts
            # elif effect.type == 'weaponcut':
            #     convertedEffects.append(effects.WeaponCut)
        
        return convertedEffects
    
    def increase_mist(self) -> None:
        self.mist_radius -= 1 if self.mist_radius > 0 else self.mist_radius
    
    def getClosestWeaponPos(self, searchedWeaponType: weapons.Weapon|None, currentPos: coordinates.Coords = None):
        closestCoords = None
        closestDistance = INFINITY

        for coords in self.terrain:
            weapon = self.terrain[coords].loot

            if (
                # take this tile's wapon into consideretion if
                # did not requested any specific searchedWeaponType
                searchedWeaponType is None
                # or the weapon is the one we are looking for
                or (
                    weapon is not None
                    and weapon == searchedWeaponType
                )
            ):
                if currentPos is None:
                    return coords
                
                distance = utils.coordinatesDistance(currentPos, coords)

                if distance < closestDistance:
                    closestCoords = coords
                    closestDistance = distance
        
        return closestCoords

class MenhirCalculator:
    def __init__(self, map :Map) -> None:
        self.map = map

        self.menhirPos = None
        self.mistCoordinates = []

    def setMenhirPos(self, menhirPos: coordinates.Coords) -> None:
        if not isinstance(menhirPos, coordinates.Coords):
            print("[MenhirCalculator] Trying to set menhir pos to non Coords object (" + str(menhirPos) + " of type " + str(type(menhirPos)) + ")")
        self.menhirPos = menhirPos
    
    def addMist(self, mistPos: coordinates.Coords) -> None:
        if mistPos not in self.mistCoordinates:
            self.mistCoordinates.append(mistPos)
    
    def isMenhirPosFound(self) -> bool:
        return self.menhirPos is not None
    
    def approximateMenhirPos(self, tick :int = None) -> coordinates.Coords:
        mistRadius = self.map.mist_radius

        if self.menhirPos is not None:
            return self.menhirPos, 1
        
        mistCoordinates = self.mistCoordinates
        if len(mistCoordinates) == 0:
            return None, None
        
        bestMenhirPos = None
        bestMistAmount = 0

        for try_menhir_y in range(self.map.size[1]):
            for try_menhir_x in range(self.map.size[0]):
                try_menhir = coordinates.Coords(try_menhir_x, try_menhir_y)

                if try_menhir in mistCoordinates:
                    continue

                mistFound = 0
                mistMax = 0

                for coords in self.map.terrain:
                    if tick is not None and hasattr(self.map.terrain[coords], 'tick'):
                        if self.map.terrain[coords].tick < tick - 16:
                            continue
                    
                    distance = int(((coords.x - try_menhir.x) ** 2 +
                                    (coords.y - try_menhir.y) ** 2) ** 0.5)
                    
                    if distance >= mistRadius:
                        mistMax += 1

                        if effects.Mist in self.map.terrain[coords].effects:
                            mistFound += 1
                    
                    if distance < mistRadius:
                        if effects.Mist in self.map.terrain[coords].effects:
                            mistFound -= 1
                
                if mistMax == 0:
                    # no mist should be found = it was not seen yet
                    # -> make proportion = 0 (this case doesnt give any information)
                    mistMax = 1
                    mistFound = 0

                if mistFound < 0:
                    mistFound = 0
                
                if mistFound/mistMax > bestMistAmount:
                    bestMenhirPos = try_menhir
                    bestMistAmount = mistFound/mistMax
        
        return bestMenhirPos, bestMistAmount
