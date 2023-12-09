import random
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles
from gupb.model import weapons
from gupb.model import consumables

from gupb.controller.ares.ares_utils import *
from gupb.controller.ares.ares_map import Map

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
    
    '''---------------------------- STRATEGIES ----------------------------'''
    
    def strategyManager(self, strategiesList):
        action = None
        for strategy in strategiesList:
            func = strategy['func']
            funcArgs = strategy['args']
            action = func(funcArgs)
            if action is not None:
                return action
            
    def mistStrategy(self, args):
        action = None
        mistPath, mistTile = self.avoidMist()
        if len(mistPath) > 0:
            self.actionsToMake, self.actionsTarget = mistPath, mistTile
            action = self.followTarget()
        return action
    
    def potionStrategy(self, args):
        action = None
        potionPath, potionTile = self.mapBase.findTarget(
            consumables.ConsumableDescription('potion'), 
            radius=self.tileNeighbourhood
        )
        if potionPath != [] and len(potionTile) < self.tileNeighbourhood:
                self.actionsToMake, self.actionsTarget = potionPath, potionTile
                action = self.followTarget()
        return action

    def findBowStrategy(self, args):
        action = None
        currentWeaponName = args[0]
        bowPath = []
        if currentWeaponName != 'bow':
            bowPath, bowTile = self.mapBase.findTarget(
                weapons.WeaponDescription('bow')
            )
            if len(bowPath) > 0:
                self.actionsToMake, self.actionsTarget = bowPath, bowTile
                action = self.followTarget()
        return action
    
    def attackFrontStrategy(self, args):
        action = None
        currentWeaponName = args[0]
        inFrontTile = args[1]
        inRightTile = args[2]
        inLeftTile = args[3]
        inBackTile = args[4]
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
        return action
    
    def variantAttackStrategy(self, args):
        action = None
        currentWeaponName = args[0]
        if currentWeaponName=="bow_unloaded":
            action=characters.Action.ATTACK
        elif currentWeaponName=="amulet" and self.amuletCharactersToAttack():
            action=characters.Action.ATTACK
        elif currentWeaponName=="axe" and self.axeCharactersToAttack():
            action=characters.Action.ATTACK
        elif currentWeaponName=="bow_loaded" and self.bowCharactersToAttack():
            action=characters.Action.ATTACK
        return action
    
    def continueToTarget(self, args):
        action = None
        if self.actionsToMake is not None and len(self.actionsToMake) > 0:
            action=self.followTarget()
        return action
    
    def searchPotionsStrategy(self, args):
        action = None
        if len(self.mapBase.visiblePotions)>0:
            self.actionsToMake, self.actionsTarget = self.pathNearestPotion()
            if len(self.actionsToMake)>0:
                action = self.followTarget()
        return action
    
    def upgradeWeaponStrategy(self, args):
        action = None
        currentWeaponName = args[0]
        if currentWeaponName=="knife" and len(self.mapBase.visibleWeapons)>0:
            self.actionsToMake, self.actionsTarget = self.lookingForWeapon()
            if len(self.actionsToMake)>0:
                action = self.followTarget()
        return action
    
    def menhirStrategy(self, args):
        action = None
        if self.mapBase.menhir:
            menhirPath, menhirTile = self.mapBase.findTarget(self.mapBase.menhir)
            if len(menhirPath) > self.tileNeighbourhood:
                self.actionsToMake, self.actionsTarget = menhirPath, menhirTile
                action = self.followTarget()
        return action
    
    def explorationStrategy(self, args):
        action = None
        # map exploration
        firstCoord=random.randint(0, self.mapBase.MAPSIZE[0]-1)
        secondCoord=random.randint(0, self.mapBase.MAPSIZE[1]-1)
        coordToExplore=coordinates.Coords(firstCoord, secondCoord)
        for _ in range(100):
            if coordToExplore in self.mapBase.exploredList:
                firstCoord=random.randint(0, self.mapBase.MAPSIZE[0]-1)
                secondCoord=random.randint(0, self.mapBase.MAPSIZE[1]-1)
                coordToExplore=coordinates.Coords(firstCoord, secondCoord)
            else:
                self.actionsToMake, self.actionsTarget = self.mapBase.findTarget(coordToExplore)
                if len(self.actionsToMake)>0:
                    action = self.followTarget()
                    return action
        return action
            
    def choice(self):
        inFrontCoords, inBackCoords, inRightCoords, inLeftCoords=self.getCoordsTiles()
        inFrontTile=self.mapBase.map[inFrontCoords.x][inFrontCoords.y]
        inBackTile=self.mapBase.map[inBackCoords.x][inBackCoords.y]
        inRightTile=self.mapBase.map[inRightCoords.x][inRightCoords.y]
        inLeftTile=self.mapBase.map[inLeftCoords.x][inLeftCoords.y]
        currentWeaponName=self.mapBase.description.weapon.name

        strategies = [
            # {'func': _, 'args': _},
            {'func': self.attackFrontStrategy, 'args': [currentWeaponName, inFrontTile, inRightTile, inLeftTile, inBackTile]},
            {'func': self.mistStrategy, 'args': []},
            {'func': self.variantAttackStrategy, 'args': [currentWeaponName]},
            {'func': self.continueToTarget, 'args': []},
            {'func': self.potionStrategy, 'args': []},
            {'func': self.searchPotionsStrategy, 'args': []},
            {'func': self.upgradeWeaponStrategy, 'args': [currentWeaponName]},
            {'func': self.menhirStrategy, 'args': []},
            {'func': self.findBowStrategy, 'args': [currentWeaponName]},
            {'func': self.explorationStrategy, 'args': []}
        ]
        action = self.strategyManager(strategies)
        if action not in POSSIBLE_ACTIONS:
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
    
    def findingPathToAttack(self):
        for key, value in self.mapBase.visibleOpponents.items():
            if value.health>self.mapBase.description.health: # if opponent has greater health than we have - dont attack
                pass
            else:
                # to be continued depending of our weapon and opponent's weapon
                pass


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
                if key.y==self.mapBase.position.y:
                    return True
            else:
                if key.x==self.mapBase.position.x:
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