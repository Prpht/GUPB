from enum import Enum
import random

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles
from gupb.model import weapons
from gupb.model import consumables
from gupb.model import effects

def logger(msg):
    with open("gupb\\controller\\ares\\logs.txt", "a") as myfile:
        myfile.write(f"{msg}\n") 


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT
]

def tileIsMist(tile):
    for effect in tile.effects:
        if effect.type == 'mist':
            return True
    return False

def tilePassable(tile):
    if type(tile) == tiles.TileDescription:
        if tile.type in ['land', 'menhir']:
            return True
    elif type(tile) == tiles.Tile:
        return tile.passable
    return False

class Map():
    '''Gathers and keeps information about the state of the arena'''

    def __init__(self, arena_description: arenas.ArenaDescription):
        '''Make new map in the knowledge base'''
        self.arena = arenas.Arena.load(arena_description.name)
        self.MAPSIZE = self.arena.size  # no arena is bigger than 100
        self.map = None
        self.initMap()  # map constructed from given knowledge
        self.opponentsAlive = 0  # how many opponents are alive
        self.description = None  # description of our champion
        self.position = None  # current position
        self.visibleOpponents = {}  # dictionary - (Coord, CharacterDescription) for every currently visible opponent
        self.closestMist = None  # coord
        self.menhir=None # coords of menhir
        self.previousHealth=None
        self.visiblePotions= []
        self.visibleWeapons= {}

    def initMap(self):
        self.map = [[None for i in range(self.MAPSIZE[1])] for j in range(self.MAPSIZE[0])]
        for coords, tile in self.arena.terrain.items():
            self.map[coords.x][coords.y] = tile
    
    def update(self, knowledge: characters.ChampionKnowledge):
        '''
        Update map with the knowledge gathered this round:
            adds current position to history, 
            updates number of steps,
            updates number of visibleOpponents,
            adds new map elements
        '''
        self.visibleOpponents={} # only if we see them right know 
        self.visiblePotions=[]
        self.position = knowledge.position
        if self.description:
            self.previousHealth=self.description.health
        self.description = knowledge.visible_tiles[self.position].character
        self.opponentsAlive = knowledge.no_of_champions_alive - 1  # not including us
        for coord, tile in knowledge.visible_tiles.items():
            coord=coordinates.Coords(coord[0], coord[1])
            self.map[coord.x][coord.y]=tile
            if self.menhir is None and tile.type=="menhir":
                self.menhir=coord
            if tile.character and tile.character.controller_name!='AresControllerNike':
                self.visibleOpponents[coord]=tile.character
            if tile.consumable:
                self.visiblePotions.append(coord)
            if tile.loot:
                self.visibleWeapons[coord]=tile.loot.name
    
    def taxiDistance(self, root, target):
        '''Return taxi distance between two points.'''
        return abs(root.x - target.x) + abs(root.y - target.y)

    def isInMap(self, coord):
        '''Check if coordinates belong within the map.'''
        if coord.x < self.MAPSIZE[0] and coord.x >= 0 and coord.y < self.MAPSIZE[1] and coord.y >= 0:
            return True
        return False

    def getNeighbours(self, root, mode=''):
        '''Return coordinates that have tiles neighbouring with root.'''
        all = [
            coordinates.Coords(root.x+1, root.y),
            coordinates.Coords(root.x-1, root.y),
            coordinates.Coords(root.x, root.y+1),
            coordinates.Coords(root.x, root.y-1)
        ]
        neighbours = []
        for new in all:
            if self.isInMap(new):
                tile = self.map[new.x][new.y]
                if (tilePassable(tile) and not tileIsMist(tile)) or mode != '':
                    neighbours.append(new)
        return neighbours
    
    def getTargetFace(self, X, Y):
        x, y = X.x - Y.x, X.y - Y.y
        if x == 0:
            return characters.Facing.UP if y > 0 else characters.Facing.DOWN
        else:  #elif y == 0:
            if(y != 0):
                raise Exception("WRONG TARGET FACE")
            return characters.Facing.LEFT if x > 0 else characters.Facing.RIGHT
    
    def dirChange(self, current, face, step):
        '''
        Returns a list of direction changes and a new facing direction 
        when moving from 'current' tile to 'step' tile
        '''
        current_face = face
        target_face = self.getTargetFace(current, step)
        if target_face == current_face:
            return [], current_face
        for axis in [[characters.Facing.UP, characters.Facing.DOWN], [characters.Facing.RIGHT, characters.Facing.LEFT]]:
            if target_face in axis and current_face in axis:
                return [characters.Action.TURN_RIGHT, characters.Action.TURN_RIGHT], target_face
        res = [characters.Action.TURN_LEFT]
        arr = [current_face, target_face]
        right_possibilities = [
            [characters.Facing.UP, characters.Facing.RIGHT],
            [characters.Facing.RIGHT, characters.Facing.DOWN],
            [characters.Facing.DOWN, characters.Facing.LEFT],
            [characters.Facing.LEFT, characters.Facing.UP]
        ]
        if arr in right_possibilities:
            res =  [characters.Action.TURN_RIGHT]
        return res, target_face
    
    def showActions(self, actions):
        str_action = ""
        for a in actions:
            if a == characters.Action.STEP_FORWARD:
                str_action = "FORWARD"
            elif a == characters.Action.TURN_RIGHT:
                str_action = "RIGHT"
            elif a == characters.Action.TURN_LEFT:
                str_action = "LEFT"
            elif a == characters.Action.DO_NOTHING:
                str_action = "NONE"
            else:
                str_action = "ATTACK"
        return str_action
        
    def getActions(self, position, path):
        '''Returns a list of actions needed to be performed to walk the given path.'''
        actions = []
        current_face = self.description.facing
        current_pos = position

        for next_pos in path:
            dirs, current_face = self.dirChange(current_pos, current_face, next_pos)
            for d in dirs:
                actions.append(d)
            # step forward
            actions.append(characters.Action.STEP_FORWARD)
            current_pos = next_pos
        return actions

    def targetFound(self, v, target):
        '''
        Verifies if coordinates v are compatible with target.
        For a list of possible targets, look to findTarget function. 
        If the target is not compliant with the list, False will be returned.
        '''
        if type(target) is str:
            if target == 'passable':
                tile = self.map[v.x][v.y]
                return tile.passable and not tileIsMist(tile)
            elif target == 'non-mist':
                return not tileIsMist(self.map[v.x][v.y])
        if type(target) is coordinates.Coords:
            if v.x == target.x and v.y == target.y:
                return True
        tile = self.map[v.x][v.y]
        if type(target) is tiles.TileDescription:
            if tile.type == target.type:
                return True
        if type(target) is weapons.WeaponDescription:
            if tile.loot is not None and tile.loot.name == target.name:
                return True
        if type(target) is consumables.ConsumableDescription:
            if tile.consumable is not None and tile.consumable.name == target.name:
                return True
        if type(target) is effects.EffectDescription:
            for effect in tile.effects:
                if effect.type == target.type:
                    return True
        return False

    def shortestPath(self, root, target, radius = None, mode=''):
        '''
        find shortest path from A to B using the knowledge base
        
        return: tuple = (array of actions to take to get from root to target, target coordinates).
        mode = 'middle' indicates that a path can lead through non-passable tiles
        '''
        Visited = [[(0 if self.map[i][j] is not None else None) for j in range(self.MAPSIZE[1])] for i in range(self.MAPSIZE[0])] 
        Visited[root.x][root.y] = root
        Q = [root]
        r = 0
        while len(Q) > 0 and (radius is None or r <= radius):
            r += 1
            v = Q.pop(0)
            if self.targetFound(v, target):
                # find path
                path = [v]
                found = v
                while Visited[v.x][v.y] is not v:
                    path.append(Visited[v.x][v.y])
                    v = Visited[v.x][v.y]
                path.pop()  # remove root from path
                path.reverse()
                return self.getActions(root, path), found
            for p in self.getNeighbours(v, mode):
                if Visited[p.x][p.y] == 0:
                    # unvisited
                    Visited[p.x][p.y] = v
                    Q.append(p)
        return [], self.position

    def findTarget(self, target, radius=None):
        '''
        finds nearest coordinate, tile type, collectible type, 

        target - acceptable formats:
            str:
                'passable' - finds closest passable tile
            coordinates.Coords
            tiles.TileDescription - closest tile with the same type
            weapons.WeaponDescription - closest tile with a weapon of the same type
            consumables.ConsumableDescription - closest tile with a consumable of the same type
            effects.EffectDescription - closest tile with an effect of the same type.

        return: tuple = (shortest path to the target, target coordinates). 
            If target not found, returns tuple = ([], self.position)
        '''
        path, tile = self.shortestPath(self.position, target, radius=radius)
        return path, tile

class KnowledgeBase():
    
    def __init__(self):
        self.mapBase = None
        self.round_counter=0
        self.actionsToMake=[]
        self.actionsTarget=None
        self.tileNeighbourhood = 16
        self.facingDirection=None

    def stepPossible(self, step):
        if step == characters.Action.STEP_FORWARD:
            frontCoords=self.mapBase.description.facing.value+self.mapBase.position
            frontTile=self.mapBase.map[frontCoords.x][frontCoords.y]
            if not tilePassable(frontTile) or tileIsMist(frontTile):
                return False
        return True

    def followTarget(self):
        nextStep = None
        if len(self.actionsToMake) > 0:
            nextStep = self.actionsToMake[0]
            self.actionsToMake.pop(0)
            if not self.stepPossible(nextStep):
                self.actionsToMake=[]
                self.actionsTarget=None
                nextStep = None
        if nextStep is None:
            self.actionsToMake=[]
            self.actionsTarget=None
            inFrontCoords, inBackCoords, inRightCoords, inLeftCoords=self.getCoordsTiles()
            inFrontTile=self.mapBase.map[inFrontCoords.x][inFrontCoords.y]
            inBackTile=self.mapBase.map[inBackCoords.x][inBackCoords.y]
            inRightTile=self.mapBase.map[inRightCoords.x][inRightCoords.y]
            inLeftTile=self.mapBase.map[inLeftCoords.x][inLeftCoords.y]
            nextStep = self.checkPossibleAction(inFrontTile, inRightTile, inLeftTile, inBackTile)

        return nextStep
    
    def avoidMist(self):
        target = 'non-mist'
        mistPath, mistTile = self.mapBase.findTarget(target)
        return mistPath, mistTile


    def choice(self):
        '''
        Return one of the choices described in POSSIBLE_ACTIONS.

        Additionally, it could take into account changing weapons, strategy, ect.
        
        '''
        inFrontCoords, inBackCoords, inRightCoords, inLeftCoords=self.getCoordsTiles()
        inFrontTile=self.mapBase.map[inFrontCoords.x][inFrontCoords.y]
        inBackTile=self.mapBase.map[inBackCoords.x][inBackCoords.y]
        inRightTile=self.mapBase.map[inRightCoords.x][inRightCoords.y]
        inLeftTile=self.mapBase.map[inLeftCoords.x][inLeftCoords.y]
        currentWeaponName=self.mapBase.description.weapon.name
        try:
            mistPath, mistTile = self.avoidMist()

            potionPath, potionTile = self.mapBase.findTarget(
                consumables.ConsumableDescription('potion'), 
                radius=self.tileNeighbourhood
            )

            bowPath = []
            if currentWeaponName != 'bow':
                bowPath, bowTile = self.mapBase.findTarget(
                    weapons.WeaponDescription('bow')
                )

            if inFrontTile.character: # depending on a weapon
                if currentWeaponName!="amulet":
                    action=characters.Action.ATTACK
                else:
                    if tilePassable(inRightTile):
                        action=characters.Action.STEP_RIGHT
                    elif tilePassable(inLeftTile):
                        action=characters.Action.STEP_LEFT
                    elif tilePassable(inBackTile):
                        action=characters.Action.STEP_BACKWARD
                    else:
                        action=characters.Action.ATTACK
            elif len(mistPath) > 0:
                self.actionsToMake, self.actionsTarget = mistPath, mistTile
                action = self.followTarget()
            elif currentWeaponName=="bow_unloaded":
                action=characters.Action.ATTACK
            elif currentWeaponName=="amulet" and self.amuletCharactersToAttack():
                action=characters.Action.ATTACK
            elif currentWeaponName=="axe" and self.axeCharactersToAttack():
                action=characters.Action.ATTACK
            elif currentWeaponName=="bow_loaded" and self.bowCharactersToAttack():
                action=characters.Action.ATTACK
            elif len(self.mapBase.visiblePotions)>0:
                self.actionsToMake, self.actionsTarget = self.pathNearestPotion()
                if len(self.actionsToMake)>0:
                    action = self.followTarget()
                else:
                    action = self.checkPossibleAction(inFrontTile, inRightTile, inLeftTile, inBackTile)
            elif currentWeaponName=="knife" and len(self.mapBase.visibleWeapons)>0:
                self.actionsToMake, self.actionsTarget = self.lookingForWeapon()
                if len(self.actionsToMake)>0:
                    action = self.followTarget()
                else:
                    action = self.checkPossibleAction(inFrontTile, inRightTile, inLeftTile, inBackTile)
            elif self.round_counter<3:
                action=characters.Action.TURN_RIGHT
                self.round_counter+=1
            elif self.actionsToMake is not None and len(self.actionsToMake) > 0:
                action=self.followTarget()
            elif potionPath != [] and len(potionTile) < self.tileNeighbourhood:
                self.actionsToMake, self.actionsTarget = potionPath, potionTile
                action = self.followTarget()
            elif self.mapBase.menhir:
                self.actionsToMake, self.actionsTarget = self.mapBase.findTarget(self.mapBase.menhir)
                if len(self.actionsToMake) > self.tileNeighbourhood:
                    action = self.followTarget()
                else:
                    self.actionsToMake, self.actionsTarget = [], None
                    action = self.checkPossibleAction(inFrontTile, inRightTile, inLeftTile, inBackTile)
            elif len(bowPath) > 0:
                self.actionsToMake, self.actionsTarget = bowPath, bowTile
                action = self.followTarget()
            else:
                action = self.checkPossibleAction(inFrontTile, inRightTile, inLeftTile, inBackTile)
        except:
            action = self.checkPossibleAction(inFrontTile, inRightTile, inLeftTile, inBackTile)
        return action
    
    def pathNearestPotion(self):
        nearestPotionActions=None
        nearestPotionTarget=None
        for potion in self.mapBase.visiblePotions:
            actionsToMake, actionsTarget = self.mapBase.findTarget(potion)
            if nearestPotionActions is None or len(actionsToMake)<len(nearestPotionActions):
                nearestPotionActions=actionsToMake
                nearestPotionTarget=actionsTarget
        return nearestPotionActions, nearestPotionTarget
    
    def lookingForWeapon(self):
        nearestWeaponActions=None
        nearestWeaponTarget=None
        for key, value in self.mapBase.visibleWeapons.items():
            actionsToMake, actionsTarget = self.mapBase.findTarget(key)
            if nearestWeaponActions is None or len(actionsToMake)<len(nearestWeaponActions):
                nearestWeaponActions=actionsToMake
                nearestWeaponTarget=actionsTarget
        return nearestWeaponActions, nearestWeaponTarget


    def checkPossibleAction(self, inFrontTile: tiles.TileDescription, inRightTile:tiles.TileDescription, \
                            inLeftTile:tiles.TileDescription, inBackTile:tiles.TileDescription):
        '''checks if tile in front is passable and if not turns randomly'''
        actionsList=[
                characters.Action.TURN_LEFT, 
                characters.Action.TURN_RIGHT
            ]
        if tilePassable(inFrontTile) and not tileIsMist(inFrontTile):
            actionsList.append(characters.Action.STEP_FORWARD)
            actionsList.append(characters.Action.STEP_FORWARD)
            actionsList.append(characters.Action.STEP_FORWARD)
            actionsList.append(characters.Action.STEP_FORWARD)
        if tilePassable(inRightTile) and not tileIsMist(inRightTile):
            actionsList.append(characters.Action.STEP_RIGHT)
        if tilePassable(inLeftTile) and not tileIsMist(inLeftTile):
            actionsList.append(characters.Action.STEP_LEFT)
        if tilePassable(inBackTile) and not tileIsMist(inBackTile):
            actionsList.append(characters.Action.STEP_BACKWARD)
        return random.choice(actionsList)
        
    def getCoordsTiles(self):
        '''getting coords of surrounding tiles'''
        currentPosition, facingCoords=self.mapBase.position, self.mapBase.description.facing.value
        inFrontCoords=facingCoords+currentPosition
        if facingCoords.x==0 and facingCoords.y==1:
            self.facingDirection="up"
            inBackCoords=currentPosition+coordinates.Coords(0, -1)
            inRightCoords=currentPosition+coordinates.Coords(1, 0)
            inLeftCoords=currentPosition+coordinates.Coords(-1, 0)
        elif facingCoords.x==0 and facingCoords.y==-1:
            self.facingDirection="down"
            inBackCoords=currentPosition+coordinates.Coords(0, 1)
            inRightCoords=currentPosition+coordinates.Coords(-1, 0)
            inLeftCoords=currentPosition+coordinates.Coords(1, 0)
        elif facingCoords.x==1 and facingCoords.y==0:
            self.facingDirection="right"
            inBackCoords=currentPosition+coordinates.Coords(-1, 0)
            inRightCoords=currentPosition+coordinates.Coords(0, -1)
            inLeftCoords=currentPosition+coordinates.Coords(0, 1)
        else:
            self.facingDirection="left"
            inBackCoords=currentPosition+coordinates.Coords(1, 0)
            inRightCoords=currentPosition+coordinates.Coords(0, 1)
            inLeftCoords=currentPosition+coordinates.Coords(0, -1)
        
        return inFrontCoords, inBackCoords, inRightCoords, inLeftCoords
    
    def amuletCharactersToAttack(self):
        '''checks if there are characters to be attacked by amulet in our range'''
        coordsInRange=[(1, 1), (-1, 1), (1, -1), (-1, -1), (2, 2),(-2, 2), (2, -2), (-2, -2)]
        for element in coordsInRange:
            coordInRange=coordinates.Coords(element[0], element[1])+self.mapBase.position
            if self.mapBase.isInMap(coordInRange) and self.mapBase.map[coordInRange.x][coordInRange.y].character:
                return True
        return False
    
    def axeCharactersToAttack(self):
        '''checks if there are characters to be attacked by axe in our range'''
        if self.facingDirection=="up":
            coordsInRange=[(0, 1), (1, 1), (-1, 1)]
        elif self.facingDirection=="down":
            coordsInRange=[(0, -1), (1, -1), (-1, -1)]
        elif self.facingDirection=="right":
            coordsInRange=[(1, 0), (1, -1), (1, -1)]
        else:
            coordsInRange=[(-1, 0), (-1, -1), (-1, 1)]
        for element in coordsInRange:
            coordInRange=coordinates.Coords(element[0], element[1])+self.mapBase.position
            if self.mapBase.isInMap(coordInRange) and self.mapBase.map[coordInRange.x][coordInRange.y].character:
                return True
        return False

    def bowCharactersToAttack(self):
        '''checks if there are characters to be attacked by axe in our range'''
        for key, value in self.mapBase.visibleOpponents.items():
            if self.facingDirection in ["left", "right"]:
                if key.x==self.mapBase.position.x:
                    return True
            else:
                if key.y==self.mapBase.position.y:
                    return True
        return False
    
    def botInDanger(self):
        currentPostion=self.mapBase.position
        if self.mapBase.previousHealth is None:
            return None
        healthLoss=self.mapBase.previousHealth-self.mapBase.description.health
        if healthLoss==1:
            if tileIsMist(self.mapBase.map[currentPostion.x][currentPostion.y]):
                return "mist"
        if healthLoss==2:
            return "attacked"
        if healthLoss>2:
            return "multipleDanger"
        return None

    def update(self, knowledge: characters.ChampionKnowledge):
        self.mapBase.update(knowledge)
    
    def praise(self, score):
        '''updates stratedy based on the praise'''
        pass

    def reset(self, arena_description: arenas.ArenaDescription):
        self.mapBase = Map(arena_description)

class AresController(controller.Controller):

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.knBase = KnowledgeBase()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AresController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.knBase.update(knowledge)
        action = self.knBase.choice()
        return action

    def praise(self, score: int) -> None:
        self.knBase.praise(score)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.knBase.reset(arena_description)

    @property
    def name(self) -> str:
        return f'AresController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.LIME


POTENTIAL_CONTROLLERS = [
    AresController("Nike")
]
