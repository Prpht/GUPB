import os, random
from typing import Dict, NamedTuple, Optional, List

from gupb.model import arenas, tiles, coordinates, weapons, games
from gupb.model import characters, consumables, effects
from gupb.model.characters import CHAMPION_STARTING_HP

from gupb.controller.aragorn import utils
from gupb.controller.aragorn.constants import DEBUG, INFINITY, WEAPON_HIERARCHY, OUR_BOT_NAME




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

        # self.map = Map.loadRandom('random', coordinates.Coords(24, 24))
        self.map = Map.load(arena_description.name)
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

    def getCurrentWeaponDescription(self):
        return self.map.terrain[self.position].character.weapon
    
    def getCurrentWeaponName(self):
        return self.getCurrentWeaponDescription().name

    def getCurrentWeaponClass(self):
        return Map.weaponDescriptionConverter(self.getCurrentWeaponDescription())

    def hasOponentInFront(self):
        frontCell = coordinates.add_coords(self.position, self.facing.value)
        
        if frontCell in self.map.terrain and self.map.terrain[frontCell].character is not None:
            return True
        
        return False
    
    def getClosestOponentInRange(self):
        closestOponentDistance = INFINITY
        closestOponentInRange = None
        
        currentWeapon = self.getCurrentWeaponClass()

        if currentWeapon is None:
            return None

        rangeCells = currentWeapon.cut_positions(self.map.terrain, self.position, self.facing)

        for cellCoords in rangeCells:
            if cellCoords == self.position:
                # do not attack yourself
                continue

            if cellCoords in self.map.terrain and self.map.terrain[cellCoords].character is not None:
                distance = utils.coordinatesDistance(self.position, cellCoords)

                if distance < closestOponentDistance:
                    closestOponentDistance = distance
                    closestOponentInRange = self.map.terrain[cellCoords].character
        
        return closestOponentInRange

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
        current_weapon = self.getCurrentWeaponName()
   
        for coords in self.map.terrain:
            if self.map.terrain[coords].loot is not None and issubclass(self.map.terrain[coords].loot, weapons.Weapon):
                possible_new_weapon = self.map.terrain[coords].loot.__name__.lower()
                #TODO: assign correct weights for weapons when the proper usage of each of them is known
                if WEAPON_HIERARCHY[possible_new_weapon] <= WEAPON_HIERARCHY[current_weapon] :
                    continue

                distance = utils.coordinatesDistance(self.position, coords)

                if distance < minDistance:
                    minDistance = distance
                    minCoords = coords
        return [minDistance, minCoords]

    def isWeak(self):
        if self.health < 0.5 * CHAMPION_STARTING_HP:
            return True

        return False
    
    def getCurrentSection(self) -> int:
        sectionsCenters = self.map.getSectionsCenters()
        distances = []

        for sectionCenter in sectionsCenters:
            distances.append(
                utils.coordinatesDistance(self.position, sectionCenter)
            )
        
        minDistance = 9999
        minSector = 0

        for i, d in enumerate(distances):
            if d < minDistance:
                minDistance = d
                minSector = i
        
        return minSector
    
    def getOppositeSection(self):
        currentSection = self.getCurrentSection()

        if currentSection == 1:
            return 4
        if currentSection == 2:
            return 3
        if currentSection == 3:
            return 2
        if currentSection == 4:
            return 1
        
        return random.randint(1, 4)
    
    def getSectionCenterPos(self, section):
        sectionsCenters = self.map.getSectionsCenters()

        if section is None or section >= len(sectionsCenters):
            if DEBUG: print("[Memory] getSectionCenterPos(): oppositeSection is not in sections! Section is:", section)
            return None
        
        return sectionsCenters[section]
    
    def getRandomSection(self):
        return random.randint(0, 4)

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

        self.sectionsCenters = None
        self.centerPos = coordinates.Coords(round(self.size[0] / 2), round(self.size[1] / 2))

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
                            terrain[position].loot =  Map.weaponDescriptionConverter(weapons.WeaponDescription(arenas.WEAPON_ENCODING[character]().description()))
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
            self.terrain[coords].loot = Map.weaponDescriptionConverter(visible_tile_description.loot)
            self.terrain[coords].character = visible_tile_description.character
            self.terrain[coords].consumable = self.consumableDescriptionConverter(visible_tile_description.consumable)
            
            tileEffects = self.effectsDescriptionConverter(visible_tile_description.effects)
            self.terrain[coords].effects = tileEffects

            if effects.Mist in tileEffects:
                self.menhirCalculator.addMist(coords)
    
    @staticmethod
    def weaponDescriptionConverter(weaponDescription: weapons.WeaponDescription) -> weapons.Weapon:
        if weaponDescription is None or not isinstance(weaponDescription, weapons.WeaponDescription):
            return None
        
        if weaponDescription.name == 'knife':
            return weapons.Knife
        elif weaponDescription.name == 'sword':
            return weapons.Sword
        elif weaponDescription.name == 'axe':
            return weapons.Axe
        elif weaponDescription.name in ['bow' 'bow_loaded' 'bow_unloaded']:
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
    
    def getDangerousTiles(self):
        """
        Returns list of tiles that are in range of enemy weapon
        """

        dangerousTiles = []

        for coords in self.terrain:
            enemyDescription = self.terrain[coords].character
            
            if enemyDescription is not None:
                weapon = Map.weaponDescriptionConverter(enemyDescription.weapon)

                if weapon is None:
                    continue

                positions = weapon.cut_positions(self.terrain, coords, enemyDescription.facing)

                for position in positions:
                    if position not in dangerousTiles:
                        dangerousTiles.append(position)
        
        return dangerousTiles

    def getDangerousTilesWithDangerSourcePos(self, currentTick :int = None, maxTicksBehind :int = None):
        """
        Returns a dict. Keys are coords with danger, values are their sources
        """

        dangerousTiles = {}

        for coords in self.terrain:
            if currentTick is not None and maxTicksBehind is not None and hasattr(self.terrain[coords], 'tick'):
                if self.terrain[coords].tick < currentTick - maxTicksBehind:
                    continue
            
            enemyDescription = self.terrain[coords].character
            
            if enemyDescription is not None and enemyDescription.controller_name != OUR_BOT_NAME:
                weapon = Map.weaponDescriptionConverter(enemyDescription.weapon)

                if weapon is None:
                    continue

                positions = weapon.cut_positions(self.terrain, coords, enemyDescription.facing)

                for position in positions:
                    if position not in dangerousTiles:
                        dangerousTiles[position] = coords
        
        return dangerousTiles
    
    def getSectionsCenters(self):
        """
        Divides map to 5 sections and returns their centers

        ul -> up left
        ur -> up right
        dl -> down left
        dr -> dorn right

        .-----------------.
        |        |        |
        |  1   __|__   2  |
        |     |     |     |
        |-----|  0  |-----|
        |     |__ __|     |
        |  3     |     4  |      
        |        |        |
        `-----------------`
        """

        # cache
        if self.sectionsCenters is not None:
            return self.sectionsCenters
        
        # get map's center
        center = coordinates.Coords(self.size[0] / 2, self.size[1] / 2)
        center = coordinates.Coords(round(center.x), round(center.y))

        # define map corners
        ul_corner = coordinates.Coords(0, 0)
        ur_corner = coordinates.Coords(self.size[0], 0)
        dl_corner = coordinates.Coords(0, self.size[1])
        dr_corner = coordinates.Coords(self.size[0], self.size[1])

        # calculate distance from center to corners
        ul_distance = coordinates.sub_coords(ul_corner, center)
        ur_distance = coordinates.sub_coords(ur_corner, center)
        dl_distance = coordinates.sub_coords(dl_corner, center)
        dr_distance = coordinates.sub_coords(dr_corner, center)

        # get 2/3 of distance
        ul_distance = coordinates.mul_coords(ul_distance, 2/3)
        ur_distance = coordinates.mul_coords(ur_distance, 2/3)
        dl_distance = coordinates.mul_coords(dl_distance, 2/3)
        dr_distance = coordinates.mul_coords(dr_distance, 2/3)
        
        # round distance to ensure that section's center coords are integers
        ul_distance = coordinates.Coords(round(ul_distance.x), round(ul_distance.y))
        ur_distance = coordinates.Coords(round(ur_distance.x), round(ur_distance.y))
        dl_distance = coordinates.Coords(round(dl_distance.x), round(dl_distance.y))
        dr_distance = coordinates.Coords(round(dr_distance.x), round(dr_distance.y))

        # add distance to center to get section's center coords
        ul_center = coordinates.add_coords(center, ul_distance)
        ur_center = coordinates.add_coords(center, ur_distance)
        dl_center = coordinates.add_coords(center, dl_distance)
        dr_center = coordinates.add_coords(center, dr_distance)

        # find closest land tile to section's center
        ul_center = utils.closestTileFromWithCondition(ul_center, lambda coords: self.terrain[coords].__class__.__name__.lower() == 'land', 30, ul_center)
        ur_center = utils.closestTileFromWithCondition(ur_center, lambda coords: self.terrain[coords].__class__.__name__.lower() == 'land', 30, ur_center)
        dl_center = utils.closestTileFromWithCondition(dl_center, lambda coords: self.terrain[coords].__class__.__name__.lower() == 'land', 30, dl_center)
        dr_center = utils.closestTileFromWithCondition(dr_center, lambda coords: self.terrain[coords].__class__.__name__.lower() == 'land', 30, dr_center)
        
        # return section's centers
        self.sectionsCenters = [
            center,
            ul_center,
            ur_center,
            dl_center,
            dr_center
        ]

        return self.sectionsCenters


class MenhirCalculator:
    def __init__(self, map :Map) -> None:
        self.map = map

        self.menhirPos = None
        self.mistCoordinates = []
        self.recentlyChanged = True

    def setMenhirPos(self, menhirPos: coordinates.Coords) -> None:
        if not isinstance(menhirPos, coordinates.Coords):
            print("[MenhirCalculator] Trying to set menhir pos to non Coords object (" + str(menhirPos) + " of type " + str(type(menhirPos)) + ")")
        self.menhirPos = menhirPos
    
    def addMist(self, mistPos: coordinates.Coords) -> None:
        if mistPos not in self.mistCoordinates:
            self.recentlyChanged = True
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
        
        if not self.recentlyChanged:
            return self.lastResult
        
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
        
        self.recentlyChanged = False
        self.lastResult = (bestMenhirPos, bestMistAmount)
        return self.lastResult
