import random

from gupb.model import arenas, characters, consumables, coordinates, weapons, effects
from gupb.model.characters import CHAMPION_STARTING_HP
from gupb.model.profiling import profile

from gupb.controller.aragorn import utils
from gupb.controller.aragorn.constants import DEBUG, INFINITY, WEAPON_HIERARCHY

from .environment import Environment
from .map import Map



class Memory:
    def __init__(self):
        self.tick = 0

        self.idleTime = 0
        self.position: coordinates.Coords = None
        self.lastPosition: coordinates.Coords = None
        self.facing: characters.Facing = characters.Facing.random()
        self.weaponDescription: weapons.WeaponDescription = (weapons.Knife()).description()
        self.no_of_champions_alive: int = 0
        self.numberOfVisibleTiles: int = 0
        
        self.map: Map = None
        self.environment: Environment = None

        self.health: int = 0
        self.last_health: int = 0
        
        # create last actions variable that
        # is a list of last 5 actions
        # with rotation actions removed
        self.lastActions: list = []
        self.debugCoords = None
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.tick = 0

        self.idleTime = 0
        self.position: coordinates.Coords = None
        self.lastPosition: coordinates.Coords = None
        self.facing: characters.Facing = characters.Facing.random()
        self.weaponDescription: weapons.WeaponDescription = (weapons.Knife()).description()
        self.no_of_champions_alive: int = 0
        self.numberOfVisibleTiles: int = 0

        # self.map = Map.loadRandom('random', coordinates.Coords(24, 24))
        self.map = Map.load(arena_description.name, memory=self)
        self.environment = Environment(self.map)

        self.health: int = 0
        self.last_health: int = 0
        
        self.lastActions: list = []
        self.debugCoords = None
    
    def update(self, knowledge: characters.ChampionKnowledge) -> None:
        self.tick += 1

        self.lastPosition = self.position
        self.position = knowledge.position
        self.facing = knowledge.visible_tiles[self.position].character.facing
        self.weaponDescription = knowledge.visible_tiles[self.position].character.weapon
        self.no_of_champions_alive = knowledge.no_of_champions_alive

        self.map.parseVisibleTiles(knowledge.visible_tiles, self.tick)

        self.numberOfVisibleTiles = len(knowledge.visible_tiles)
        
        self.idleTime += 1
        self.environment.environment_action(self.no_of_champions_alive)

        self.health = knowledge.visible_tiles[self.position].character.health
        self.debugCoords = None

        # fix error of not always seeing cut effect on my coords
        # (it may be cleared by game before we see it)
        if self.health < self.last_health:
            if self.map.terrain[self.position].effects is None:
                self.map.terrain[self.position].effects = []
            if effects.WeaponCut not in self.map.terrain[self.position].effects:
                self.map.terrain[self.position].effects.append(effects.WeaponCut)
        # =====================
        
        self.last_health = self.health

    def addLastAction(self, action):
        self.lastActions.append(action)
        self.lastActions = self.lastActions[-5:]
    
    def getLastActions(self):
        return self.lastActions

    def getCurrentWeaponDescription(self):
        return self.weaponDescription
    
    def getCurrentWeaponName(self):
        return self.weaponDescription.name if self.weaponDescription is not None else None

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
                distance = utils.manhattanDistance(self.position, cellCoords)

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
    
    @profile
    def getDistanceToClosestPotion(self, maxTicksAgo = None):
        minDistance = INFINITY
        minCoords = None

        for coords in self.map.terrain:
            if self.map.terrain[coords].consumable == consumables.Potion:
                if (
                    maxTicksAgo is not None
                    and hasattr(self.map.terrain[coords], 'tick')
                    and self.map.terrain[coords].tick < self.tick - maxTicksAgo
                ):
                    continue

                distance = utils.manhattanDistance(self.position, coords)

                if distance < minDistance:
                    minDistance = distance
                    minCoords = coords
        
        return [minDistance, minCoords]

    @profile
    def getDistanceToClosestWeapon(self, weaponHierarchy = None):
        minDistance = INFINITY
        minCoords = None
        current_weapon = self.getCurrentWeaponName()
        
        if weaponHierarchy is None:
            weaponHierarchy = WEAPON_HIERARCHY
   
        for coords in self.map.terrain:
            if self.map.terrain[coords].loot is not None and issubclass(self.map.terrain[coords].loot, weapons.Weapon):
                possible_new_weapon = self.map.terrain[coords].loot.__name__.lower()

                if current_weapon in weaponHierarchy and weaponHierarchy[possible_new_weapon] <= weaponHierarchy[current_weapon] :
                    continue

                if self.debugCoords is None:
                    self.debugCoords = []
                self.debugCoords.append(coords)

                distance = utils.manhattanDistance(self.position, coords)

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
