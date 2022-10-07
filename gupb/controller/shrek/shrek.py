import random
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates


class ShrekController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.position = None
        self.direction = None
        self.curent_map_knowledge = {}
        self.weapon_name = 'knife'

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ShrekController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.position = None
        self.direction = None
        self.curent_map_knowledge = {}
        self.weapon_name = 'knife'


    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.position = knowledge.position
        info = knowledge.visible_tiles[self.position].character
        self.direction = info.facing
        self.current_weapon = info.weapon.name
        self.curent_map_knowledge.update(knowledge.visible_tiles)
    
   
        if self.path_blocked(knowledge):
            return self.make_a_turn()
        

        #TODO if mnist coming : RUN in riht direction - create list of direction to remember where to go
        #TODO wepoen around, get it has to be better the knife
        #later:
        #TODO go after enemy 
        #TODO remember next step for some strategy 
        #TODO remeber direction -> not go back

        if self.is_enemy_around(knowledge):
            if info.health >= characters.CHAMPION_STARTING_HP * 0.5:
                facing_tile = self.position + self.direction.value
                if  knowledge.visible_tiles[facing_tile].character:
                    return characters.Action.ATTACK
            

        return self.move()
        


    def path_blocked(self, knowledge: characters.ChampionKnowledge):
        '''
        Check if there is a obstacle blocking the path (Sea or Wall)
        '''
        facing_tile = self.position + self.direction.value
        if knowledge.visible_tiles[facing_tile].type != 'land':
            return True
        
        return False
      

    def make_a_turn(self):
        '''
        Make a random turn right or left
        '''
        POSSIBLE_TURNS= [characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
        return random.choice(POSSIBLE_TURNS)
    

    def move(self):
        '''
        Take a step forward, or turn
        '''
        rand_num = random.random()
        if rand_num <= 0.8:
            return characters.Action.STEP_FORWARD
        elif rand_num > 0.8 and rand_num <= 0.9:
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_RIGHT


    def is_enemy_around(self, knowledge: characters.ChampionKnowledge):
        '''
        Check if any enemies in sight'''
        for coordinates, tile_descr in knowledge.visible_tiles.items():
            if tile_descr.character  and coordinates != (self.position.x, self.position.y):
                return True
        return False
        



    @property
    def name(self) -> str:
        return f'ShrekController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN


POTENTIAL_CONTROLLERS = [
    ShrekController("Fiona"),
]
