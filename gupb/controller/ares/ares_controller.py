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


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

'''
Suggestion: strategy in try, excet, in case of failure random step?

Or eliminate all raise exception

'''

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
        self.opponents = []  # list of tuples (Coord, Character) for every currently visible opponent
        self.closestMist = None  # coord

    def initMap(self):
        self.map = [[None for i in range(self.MAPSIZE[1])] for j in range(self.MAPSIZE[0])]
        for coords, tile in self.arena.terrain.items():
            self.map[coords.x][coords.y] = tile

    def tileIsMist(self, tile):
        for effect in tile.effects:
            if effect.description().type == 'mist':
                return True
        return False
    
    def update(self, knowledge: characters.ChampionKnowledge):
        '''
        Update map with the knowledge gathered this round:
            adds current position to history, 
            updates number of steps,
            updates number of opponents,
            adds new map elements
        '''
        self.position = knowledge.position
        self.description = knowledge.visible_tiles[self.position].character
        self.opponentsAlive = knowledge.no_of_champions_alive - 1  # not including us
        # for coord, tile in knowledge.visible_tiles.items():
        #     coord=coordinates.Coords(coord[0], coord[1])
        #     if self.tileIsMist(tile) and \
        #         (self.closestMist is None or \
        #         (self.taxiDistance(self.position, self.closestMist) > self.taxiDistance(self.position, coord))):
        #         self.closestMist = coord
        #     if tile.character != self.map[coord.x][coord.y].character:
        #         self.map[coord.x][coord.y].character = tile.character
        #     if tile.loot != self.map[coord.x][coord.y].loot:
        #         self.map[coord.x][coord.y].loot = tile.loot
        #     if tile.consumable != self.map[coord.x][coord.y].consumable:
        #         self.map[coord.x][coord.y].consumable = tile.consumable
        #     if tile.effects != self.map[coord.x][coord.y].effects:
        #         self.map[coord.x][coord.y].effects = tile.effects

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
                if (tile.passable and not self.tileIsMist(tile)) or mode != '': # passable as an attribute???
                    neighbours.append(new)
        return neighbours
    
    def dirChange(self, current, face, step):
        '''
        Returns a list of direction changes and a new facing direction 
        when moving from 'current' tile to 'step' tile
        '''
        actions = []
        
        for _ in range(4):
            if (current.x + face.value.y) == step.x and (current.y + face.value.x) == step.y:
                break
            face = face.turn_right()
            actions.append(characters.Action.TURN_RIGHT)
        if len(actions) == 3:
            actions = [characters.Action.TURN_LEFT]
        if len(actions) == 4:
            # print("Direction not found.")
            pass
        return actions, face
        
    def getActions(self, current, path):
        '''Returns a list of actions needed to be performed to walk the given path.'''
        actions = []
        face = self.description.facing
        for step in path:
            # face right dir
            dirs, face = self.dirChange(current, face, step)
            for d in dirs:
                actions.append(d)
            # step forward
            actions.append(characters.Action.STEP_FORWARD)
            current = step
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
                return tile.passable and not self.tileIsMist(tile)
        if type(target) is coordinates.Coords:
            if v.x == target.x and v.y == target.y:
                return True
        tile = self.map[v.x][v.y]
        if type(target) is tiles.TileDescription:
            if tile.type == target.type:
                return True
        if type(target) is weapons.WeaponDescription:
            if tile.description().loot is not None and tile.description().loot.name == target.name:
                return True
        if type(target) is consumables.ConsumableDescription:
            if tile.description().consumable is not None and tile.description().consumable.name == target.name:
                return True
        if type(target) is effects.EffectDescription:
            for effect in tile.effects:
                if effect.description().type == target.type:
                    return True
        return False

    def shortestPath(self, root, target, mode=''):
        '''
        find shortest path from A to B using the knowledge base
        
        return: tuple = (array of actions to take to get from root to target, target coordinates).
        mode = 'middle' indicates that a path can lead through non-passable tiles
        '''
        Visited = [[(0 if self.map[i][j] is not None else None) for j in range(self.MAPSIZE[1])] for i in range(self.MAPSIZE[0])] 
        Visited[root.x][root.y] = root
        Q = [root]
        while len(Q) > 0:
            v = Q.pop(0)
            if self.targetFound(v, target):
                # find path
                path = [v]
                found = v
                while Visited[v.x][v.y] is not v:
                    path.append(Visited[v.x][v.y])
                    v = Visited[v.x][v.y]
                path.pop()  #remove root from path
                path.reverse()
                return self.getActions(root, path), found
            for p in self.getNeighbours(v, mode):
                if Visited[p.x][p.y] == 0:
                    # unvisited
                    Visited[p.x][p.y] = v
                    Q.append(p)
        return [], self.position

    def findTarget(self, target):
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
        return self.shortestPath(self.position, target)

    def findMiddle(self):
        '''
        Finds the best guess as to the map's middle
        Returns shortest path to middle and its coordinates (or tuple(empty list, self.position) if middle not found)
        '''
        middle = coordinates.Coords(
            self.MAPSIZE[0] // 2,
            self.MAPSIZE[1] // 2,
        )
        tile = self.map[middle.x][middle.y]
        if not tile.passable or self.tileIsMist(tile):
            _, middle = self.shortestPath(middle, 'passable', 'middle')
            return self.shortestPath(self.position, middle)
        return [], self.position


class KnowledgeBase():
    
    def __init__(self):
        self.mapBase = None
        self.round_counter=0
        self.actionsToMake=None

    def findTarget(self):
        '''Looks for opponent or worthy consumable. If opponent found, change self.MODE'''
        pass

    def fightOpponent(self):
        '''starts or continues a fight'''
        pass

    def avoidOpponent(self):
        '''Avoids fights in cases of low HP'''
        pass

    def choice(self):
        '''
        Return one of the choices described in POSSIBLE_ACTIONS.

        Additionally, it could take into account changing weapons, strategy, ect.
        
        '''
        
        inFrontCoords=self.mapBase.description.facing.value+self.mapBase.position
        inFrontTile=self.mapBase.map[inFrontCoords.x][inFrontCoords.y].description()

        if inFrontTile.character is not None:
            action=characters.Action.ATTACK
        elif self.round_counter<3:
            action=characters.Action.TURN_RIGHT
            self.round_counter+=1
        else:
            action=self.checkPossibleAction(inFrontTile)
            # print(inFrontTile.description().type)
            # self.actionsToMake=self.mapBase.findMiddle()[0]
            # self.actionsToMake=[characters.Action.STEP_FORWARD, characters.Action.STEP_FORWARD, characters.Action.STEP_FORWARD, characters.Action.STEP_FORWARD]
            # print("this is middle of the map")
            # print(middle[0])
            # print(type(middle[0]))
            # if len(self.actionsToMake)>0:
            #     to_do=self.actionsToMake.pop(1)
            #     print(to_do)
            #     print(type(to_do))
            #     # action=to_do
            # else:
                # action=random.choice(POSSIBLE_ACTIONS)
                # action=self.checkPossibleAction(inFrontTile)
            # action=characters.Action.DO_NOTHING
        # print(action)
        return action
    
    def checkPossibleAction(self, inFrontTile: tiles.TileDescription):
        '''checks if tile in front is passable and if not turns randomly'''
        # print(inFrontTile.type)
        if inFrontTile.type in ["sea", "wall"]:
            return random.choice([characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT])
        else:
            # return characters.Action.STEP_FORWARD
            return random.choice([characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD])
    
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

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
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
