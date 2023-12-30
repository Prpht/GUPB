from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles
from gupb.model import weapons
from gupb.model import consumables
from gupb.model import effects

from gupb.controller.ares.ares_utils import *



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
        self.exploredList=[] # list of explored coords

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
