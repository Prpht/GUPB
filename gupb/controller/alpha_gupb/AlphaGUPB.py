import random

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.effects import EffectDescription

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
]


class AlphaGUPB(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.all_knowledge = {}
        self.position = None
        self.champion = None
        self.facing = None

    def find_weapons(self):
        tiles_with_weapons = {}
        for tile in self.all_knowledge:
            if(self.all_knowledge[tile].loot):
                tiles_with_weapons[tile] = self.all_knowledge[tile].loot
        return tiles_with_weapons
    
    def closest_tile(self, pos, tiles):
        def distance(p1, p2):
            return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5
        return min(tiles, key=lambda tile: distance(pos, tile))


    def can_walk(self, tile):
        tile = tuple(tile)
        if(tile not in self.all_knowledge):
            return False
        if(self.all_knowledge[tile].type == 'sea'):
            return False
        if(self.all_knowledge[tile].type == 'wall'):
            return False
        return True

    def easy_access(self, tile):
        pos = list(self.position)
        if(pos[0]==tile[0] and pos[1]==tile[1]):
            return [False, False]
        diff_x = tile[0] - pos[0]
        diff_y = tile[1] - pos[1]

        if(diff_x > 0):
            x_dir = 1
        elif(diff_x == 0):
            x_dir = 0
        else:
            x_dir = -1

        if(diff_y > 0):
            y_dir = 1
        elif(diff_y == 0):
            y_dir = 0
        else:
            y_dir = -1

        path = []
        cant_go_x = False
        cant_go_y = False

        while(pos[0] != tile[0] or pos[1] != tile[1]):

            if(pos[0] != tile[0]):
                pos[0] += x_dir
                if(self.can_walk(pos)):
                    cant_go_x = False
                    path.append(pos.copy())
                    if(pos[0]==tile[0] and pos[1]==tile[1]):
                        return [True, path]
                else:
                    cant_go_x = True
                    pos[0] -= x_dir

            if(pos[1] != tile[1]):
                pos[1] += y_dir
                if(self.can_walk(pos)):
                    cant_go_y = False
                    path.append(pos.copy())
                    if(pos[0]==tile[0] and pos[1]==tile[1]):
                        return [True, path]
                else:
                    cant_go_y = True
                    pos[1] -= y_dir
                
            if(cant_go_x and cant_go_y):
                return [False, False]
            if(cant_go_x and pos[1] == tile[1]):
                return [False, False]
            if(cant_go_y and pos[0] == tile[0]):
                return [False, False]
        return [True, path]
    
    def go_right(self):
        if(self.facing == characters.Facing.RIGHT):
            return characters.Action.STEP_FORWARD
        if(self.facing == characters.Facing.LEFT):
            return characters.Action.TURN_LEFT
        if(self.facing == characters.Facing.UP):
            return characters.Action.TURN_RIGHT
        if(self.facing == characters.Facing.DOWN):
            return characters.Action.TURN_LEFT
        
    def go_left(self):
        if(self.facing == characters.Facing.RIGHT):
            return characters.Action.TURN_LEFT
        if(self.facing == characters.Facing.LEFT):
            return characters.Action.STEP_FORWARD
        if(self.facing == characters.Facing.UP):
            return characters.Action.TURN_LEFT
        if(self.facing == characters.Facing.DOWN):
            return characters.Action.TURN_RIGHT
        
    def go_up(self):
        if(self.facing == characters.Facing.UP):
            return characters.Action.STEP_FORWARD
        if(self.facing == characters.Facing.LEFT):
            return characters.Action.TURN_RIGHT
        if(self.facing == characters.Facing.RIGHT):
            return characters.Action.TURN_LEFT
        if(self.facing == characters.Facing.DOWN):
            return characters.Action.TURN_LEFT   
        
    def go_down(self):
        if(self.facing == characters.Facing.RIGHT):
            return characters.Action.TURN_RIGHT
        if(self.facing == characters.Facing.LEFT):
            return characters.Action.TURN_LEFT
        if(self.facing == characters.Facing.UP):
            return characters.Action.TURN_LEFT
        if(self.facing == characters.Facing.DOWN):
            return characters.Action.STEP_FORWARD   
            
    def is_enemy_front(self):
        front_coords = self.position + self.facing.value
        return self.all_knowledge[front_coords].character
    
    def go_to_center(self):
        if(self.position[0] > 12):
            new_pos = [self.position[0]-1, self.position[1]]
            if(self.can_walk(new_pos)):
                return self.go_left()
        elif(self.position[1] > 12):
            new_pos = [self.position[0], self.position[1]-1]
            if(self.can_walk(new_pos)):
                return self.go_up()
        if(self.position[0] < 12):
            new_pos = [self.position[0]+1, self.position[1]]
            if(self.can_walk(new_pos)):
                return self.go_right()
        if(self.position[1] < 12):
            new_pos = [self.position[0], self.position[1]+1]
            if(self.can_walk(new_pos)):
                return self.go_down()
        
        return random.choice(POSSIBLE_ACTIONS)

    def find_move(self, target_tile):
        if(target_tile[0]!=self.position[0]):
            direction = target_tile[0] - self.position[0]
            if(direction == 1):
                return(self.go_right())
            if(direction == -1):
                return(self.go_left())

        elif(target_tile[1]!=self.position[1]):
            direction = target_tile[1] - self.position[1]
            if(direction == 1):
                return(self.go_down())
            if(direction == -1):
                return(self.go_up())


    def run_away(self, tile):
        pos = list(self.position)
        if(pos[0]==tile[0] and pos[1]==tile[1]):
            return random.choice(POSSIBLE_ACTIONS)
        diff_x = tile[0] - pos[0]
        diff_y = tile[1] - pos[1]

        if(diff_x > 0):
            return self.go_left()
        elif(diff_x < 0 ):
            return self.go_right()

        if(diff_y > 0):
            return self.go_up()
        elif(diff_y < 0):
            return self.go_down()
        
        return random.choice(POSSIBLE_ACTIONS)


    def facing_mist(self):
        pos = self.position
        for tile in self.all_knowledge:
            effects = self.all_knowledge[tile].effects
            for effect in effects:
                if(isinstance(effect, EffectDescription) and effect.type == 'mist'):
                    if(abs(tile[0] - pos[0])<6 and abs(tile[1]-pos[1]) <6):
                        return [True,tile]
        return [False,False]

    def update_knowledge(self, visible_tiles):
        for visible_tile in visible_tiles:
            self.all_knowledge[visible_tile] = visible_tiles[visible_tile]

    def see_enemy(self, tiles):
        for tile in tiles:
            if(tiles[tile].character!=None and tiles[tile].character.controller_name!="AlphaGUPB"):
                return True
        return False

    def can_step_forward(self):
        new_position = self.position + self.facing.value
        return self.all_knowledge[new_position].type == 'land'

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AlphaGUPB):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.update_knowledge(knowledge.visible_tiles)
        self.position = knowledge.position
        self.facing= knowledge.visible_tiles[knowledge.position].character.facing
        self.weapon = knowledge.visible_tiles[knowledge.position].character.weapon
        if self.is_enemy_front():
            return characters.Action.ATTACK
        
        if(self.facing_mist()[0]):
            self.run_away(self.facing_mist()[1])

        self.facing_mist()
        weapons = self.find_weapons()
        if(len(weapons)==0):
            return self.go_to_center()
        else:
            closest_weapon = self.closest_tile(self.position, weapons.keys())
        if(self.easy_access(closest_weapon)[0] and self.weapon.name == 'knife' or self.weapon.name == 'Bow'):
            next_tile = tuple(self.easy_access(closest_weapon)[1][0])
            return(self.find_move(next_tile))
        else:
            return self.go_to_center()
            
       

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.YELLOW