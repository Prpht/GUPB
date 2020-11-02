import random
import math

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

def should_attack(knowledge):
    current_pos = knowledge.visible_tiles[knowledge.position]
    in_front = knowledge.visible_tiles[knowledge.position + current_pos.character.facing.value]

    return in_front.character is not None

def get_tile_type(tiles, coord):
    if(coord in tiles):
        return tiles[coord].type
    return None

class HidingSpotFinder:
    def __init__(self, controller):
        self.controller = controller
        self.shelter3tiles = []
        self.shelter2tiles = []
        
    def findHiddingSpots(self):
        self.shelter3tiles = []
        self.shelter2tiles = []
        tiles = self.controller.scanedArena
        for (key, value) in tiles.items():
            if(value.type == 'land'):
                neighbouringTiles = []

                neighbour = coordinates.add_coords(key, (0,1))
                if(get_tile_type(tiles, neighbour) == 'wall'): 
                    neighbouringTiles.append(neighbour)

                neighbour = coordinates.add_coords(key, (1,0))
                if(get_tile_type(tiles, neighbour) == 'wall'): 
                    neighbouringTiles.append(neighbour)

                neighbour = coordinates.add_coords(key, (0,-1))
                if(get_tile_type(tiles, neighbour) == 'wall'): 
                    neighbouringTiles.append(neighbour)

                neighbour = coordinates.add_coords(key, (-1,0))
                if(get_tile_type(tiles, neighbour) == 'wall'): 
                    neighbouringTiles.append(neighbour)

                if(len(neighbouringTiles) == 3):
                    self.shelter3tiles.append(key)
                if(len(neighbouringTiles) == 2 and math.dist(neighbouringTiles[0], neighbouringTiles[1]) != 2):
                    self.shelter2tiles.append(key)

    def getBestSpot(self):
        self.findHiddingSpots()
        if(len(self.shelter3tiles) > 0):
            return max(self.shelter3tiles, key=lambda c: math.dist(c, self.controller.menhirPos))
        if(len(self.shelter2tiles) > 0):
            return max(self.shelter2tiles, key=lambda c: math.dist(c, self.controller.menhirPos))
        return None


class CommandInterface:
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        pass


class DefendCommand(CommandInterface):
    def __init__(self, controller):
        self.controller = controller
        self.nextTurn = characters.Action.TURN_RIGHT

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        frontTileType = get_tile_type(self.controller.scanedArena, coordinates.add_coords(self.controller.currentPos, self.controller.facing.value))
        leftTileType = get_tile_type(self.controller.scanedArena, coordinates.add_coords(self.controller.currentPos, self.controller.facing.turn_left().value))
        rightTileType = get_tile_type(self.controller.scanedArena, coordinates.add_coords(self.controller.currentPos, self.controller.facing.turn_right().value))

        if (leftTileType != 'land' and rightTileType != 'land' and frontTileType == 'land'):
            self.nextTurn = characters.Action.DO_NOTHING
        elif (self.nextTurn == characters.Action.TURN_RIGHT and leftTileType == 'land'):
            self.nextTurn = characters.Action.TURN_LEFT
        elif (self.nextTurn == characters.Action.TURN_LEFT and rightTileType == 'land'):
            self.nextTurn = characters.Action.TURN_RIGHT
        return self.nextTurn


class HideCommand(CommandInterface):
    def __init__(self, controller):
        self.controller = controller
        self.spotFinder = HidingSpotFinder(controller)
        self.target = None
        self.currentSubcommand = None
        self.currentlyWalking = False

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if(self.target == None):
            self.target = self.spotFinder.getBestSpot()
        if(self.controller.iteration > 120):
            self.controller.currentCommand = GoToTargetCommand(self.controller, self.controller.menhirPos)
            return self.controller.currentCommand.decide(knowledge)

        if(self.target == None or (self.currentlyWalking == True and self.target == knowledge.position)):
            self.currentlyWalking = False
            self.currentSubcommand = DefendCommand(self.controller)

        if(self.currentSubcommand == None):
            self.currentlyWalking = True
            self.currentSubcommand = GoToTargetCommand(self.controller, self.target, False)
        try:
            return self.currentSubcommand.decide(knowledge)
        except Exception as e:
            self.target = None
            return self.decide(knowledge)


class GoToTargetCommand(CommandInterface):
    def __init__(self, controller, target, stopBeforeTarget = True):
        self.controller = controller
        self.target = target
        self.path = None
        self.stopBeforeTarget = stopBeforeTarget

    def createNode(self, grid: Grid, coord: coordinates.Coords) -> Grid.node:
        return grid.node(coord[0], coord[1])
    
    def isTerrainPassable(self, coord) -> bool:
        tile = self.controller.scanedArena[coord]
        return tile.type != 'sea' and tile.type != 'wall'

    def createVisibleArenaMatrix(self):
        max_X = max(self.controller.scanedArena.keys(), key=lambda coord: coord[0])[0]
        max_Y = max(self.controller.scanedArena.keys(), key=lambda coord: coord[1])[1]
        assumedArenaSize = (max(max_X, max(self.controller.menhirPos[0], self.target[0])), max(max_Y,  max(self.controller.menhirPos[1], self.target[1])))

        columns = assumedArenaSize[0]+1
        rows = assumedArenaSize[1]+1
        arenaMatrix = [[1]*columns for i in range(rows)]
        for (key, value) in self.controller.scanedArena.items():
            if(not self.isTerrainPassable(key)):
                arenaMatrix[key[1]][key[0]] = 0
        
        return arenaMatrix

    def calculatePath(self):
        arenaMatrix = self.createVisibleArenaMatrix()
        grid = Grid(matrix=arenaMatrix)
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        path, runs = finder.find_path(self.createNode(grid, self.controller.currentPos), self.createNode(grid, self.target), grid)
        return path

    def checkPath(self):
        if(self.path == None):
            return False
        for coord in self.path:
            if(coord not in self.controller.scanedArena): 
                continue
            tile = self.controller.scanedArena[coord]
            if(not self.isTerrainPassable(coord)):
                return False
        return True

    def getPath(self):
        if(self.checkPath()):
            return self.path
        return self.calculatePath()

    def nextStep(self):
        path = self.getPath()
        if(path[0] == self.controller.currentPos):
            path.pop(0)
        self.path = path
        nextPos = path[0] # first element equals current position
        if ((self.stopBeforeTarget and nextPos == self.target) or self.controller.currentPos == self.target):
            self.controller.currentCommand = DefendCommand(self.controller)
            return characters.Action.DO_NOTHING
        if(self.controller.currentPos + self.controller.facing.value == nextPos):
            return characters.Action.STEP_FORWARD
        elif(self.controller.currentPos + self.controller.facing.turn_left().value == nextPos):
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_RIGHT

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.nextStep()


class IdentifyFacingCommand(CommandInterface):
    def __init__(self, controller):
        self.controller = controller
        self.iteration = 0
        self.previusPos = controller.currentPos

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        action = None
        currentPos = knowledge.position
        if(self.iteration == 0):
            action = characters.Action.STEP_FORWARD
            self.iteration += 1
        elif(self.iteration == 1):
            if(self.previusPos == currentPos):
                action = characters.Action.TURN_RIGHT
                self.iteration = 0
            else:
                self.controller.facing = characters.Facing(coordinates.sub_coords(currentPos, self.previusPos))
                self.controller.currentCommand = ScanCommand(self.controller)
                action = self.controller.currentCommand.decide(knowledge)
        self.previusPos = currentPos
        return action


class ScanCommand(CommandInterface):
    def __init__(self, controller):
        self.controller = controller
        self.iteration = 0

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.iteration += 1

        if (self.iteration == 4):
            self.controller.currentCommand = HideCommand(self.controller)
            return self.controller.currentCommand.decide(knowledge)

        return characters.Action.TURN_RIGHT


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BBBotController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.scanedArena = {}
        self.currentPos = coordinates.Coords(0,0)
        self.facing = characters.Facing.UP # temporary facing
        self.currentCommand = IdentifyFacingCommand(self)
        self.iteration = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BBBotController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.__init__(self.first_name)
        self.menhirPos = arena_description.menhir_position
        
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.iteration += 1
        self.currentPos = knowledge.position
        self.scanedArena.update(knowledge.visible_tiles)
        if should_attack(knowledge):
            return characters.Action.ATTACK
        action = self.currentCommand.decide(knowledge)
        if(action == characters.Action.TURN_LEFT):
            self.facing = self.facing.turn_left()
        elif(action == characters.Action.TURN_RIGHT):
            self.facing = self.facing.turn_right()
        return action

    @property
    def name(self) -> str:
        return f'BBBotController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE


POTENTIAL_CONTROLLERS = [
    BBBotController("Bartek"),
]
