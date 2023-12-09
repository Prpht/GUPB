import random
from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.tiles import TileDescription
from gupb.model.effects import EffectDescription
from gupb.controller.alpha_gupb.pathfinder import pathfinder
import copy
from typing import NamedTuple, Optional, List
from gupb.controller.alpha_gupb.movement.movement import go_down, go_left, go_right, go_up
from gupb.controller.alpha_gupb.combat.combat import attackable_tiles, attack_enemy, can_attack_check
from gupb.model import arenas

from collections import defaultdict

POSSIBLE_ACTIONS = [
    characters.Action.TURN_RIGHT,
    characters.Action.TURN_LEFT,
    characters.Action.STEP_FORWARD
]


class AlphaGUPB(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.all_knowledge = {}
        self.positions = []
        self.knowledge_age = defaultdict(int)
        self.position = None
        self.champion = None
        self.facing = None
        self.menhir = None
        self.closest_enemy = None
        self.mist = []
        self.walkable_tiles = []
        self.seen_tiles = set()

        

    def find_weapons(self):
        tiles_with_weapons = {}
        for tile in self.all_knowledge:
            if(self.all_knowledge[tile].loot and self.all_knowledge[tile].loot.name not in ['amulet', 'bow_loaded', 'bow_unloaded', 'Amulet']):
                tiles_with_weapons[tile] = self.all_knowledge[tile].loot
        return tiles_with_weapons
    
    def find_potion(self):
        tiles_with_potions = []
        for tile in self.all_knowledge:
            if(self.all_knowledge[tile].consumable and self.all_knowledge[tile].consumable.name == 'potion'):
                tiles_with_potions.append(tile)
        return tiles_with_potions
    
    def distance(self, p1, p2):
        return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

    def closest_tile(self, pos, tiles):
        if(len(tiles) == 1):
            tiles = list(tiles)
            if(tiles[0][0] == self.position[0] and tiles[0][1] ==self.position[1]):
                return False
            else:
                return tiles[0]
        def distance(p1, p2):
            return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5
        
        # Filter out the pos tile from the list of tiles
        filtered_tiles = [tile for tile in tiles if tile != pos]
        
        # Return the closest tile from the filtered list
        return min(filtered_tiles, key=lambda tile: distance(pos, tile))

    def furthest_tiles(self, pos, tiles):
        def distance(p1, p2):
            return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5
        filtered_tiles = [tile for tile in tiles if tile != pos]
        sorted_tiles = sorted(filtered_tiles, key=lambda tile: distance(pos, tile), reverse=True)
        return sorted_tiles

    def furthest_tile_from_enemy(self, furthest_tiles, enemy):
        for tile in furthest_tiles:
            if(self.distance(self.position, tile) < self.distance(enemy, tile)):
                return tile
        return []
    
    def not_walked_tiles(self):
        tiles = []
        for tile in self.all_knowledge:
            if(tile not in self.seen_tiles and self.can_walk(tile)):
                tiles.append(tile)
        return tiles


    def get_blocks(self, knowledge):
        blocks = []
        for tile in knowledge:
            walkable = self.can_walk(tile)
            block = {"x": tile[0], "y": tile[1], "walkable":walkable}
            blocks.append(block)
        return blocks

    def can_walk(self, tile):
        tile = tuple(tile)
        if(tile not in self.all_knowledge):
            return False
        if(self.all_knowledge[tile].type == 'sea'):
            return False
        if(self.all_knowledge[tile].type == 'wall'):
            return False
        return True

        
            
    def is_enemy_front(self):
        front_coords = self.position + self.facing.value
        return self.all_knowledge[front_coords].character
    

    def find_move(self, target_tile):
        if(target_tile[0]!=self.position[0]):
            direction = target_tile[0] - self.position[0]
            if(direction == 1):
                return(go_right(self.facing))
            if(direction == -1):
                return(go_left(self.facing))

        elif(target_tile[1]!=self.position[1]):
            direction = target_tile[1] - self.position[1]
            if(direction == 1):
                return(go_down(self.facing))
            if(direction == -1):
                return(go_up(self.facing))




    def get_enemies(self, tiles):
        enemies = {}
        for tile in tiles:
            if(tiles[tile].character and tiles[tile].character.controller_name!="AlphaGUPB"):
                enemies[tuple(tile)] = tiles[tile].character
        return enemies




    def get_mist(self):
        tiles = []
        for tile in self.all_knowledge:
            effects = self.all_knowledge[tile].effects
            for effect in effects:
                if(isinstance(effect, EffectDescription) and effect.type == 'mist'):
                    tiles.append(tile)
        return tiles
    
    def get_menhir(self):
        for tile in self.all_knowledge:
            if(self.all_knowledge[tile].type == 'menhir'):
                return tile
        return None
    
    def get_closest_mist(self, tiles):
        pos_x = self.position[0]
        pos_y = self.position[1]
        closest_tiles = []
        for tile in tiles:
            min_distance_x = 999
            min_distance_y = 999

            tile_distance_x = abs(pos_x - tile[0])
            tile_distance_y = abs(pos_y - tile[1])
            if(tile_distance_x <= min_distance_x or tile_distance_y <= min_distance_y):
                closest_tiles.append(tile)
            min_distance_x = min(min_distance_x, tile_distance_x)
            min_distance_y = min(min_distance_y, tile_distance_y)

        return closest_tiles

    def get_tiles_next_to_mist(self, tiles_with_mist):
        tiles_next_to_mist = []
        pos_x = self.position[0]
        pos_y = self.position[1]
        for tile in tiles_with_mist:
            if(tile[0] > pos_x):
                x = tile[0]-3
            else:
                x = tile[0]+3

            if(tile[1] > pos_y):
                y = tile[1]-3
            else:
                y = tile[1]+3
            tiles_next_to_mist.append((x,y))
        return tiles_next_to_mist

                    
    def update_knowledge(self, visible_tiles):
        for visible_tile in visible_tiles:
            self.all_knowledge[visible_tile] = copy.copy(visible_tiles[visible_tile])
            self.knowledge_age[visible_tile] = 0

        tiles_to_delete = []
        for tile in self.knowledge_age:
            self.knowledge_age[tile] +=1
            if(self.knowledge_age[tile]> 6):
                tiles_to_delete.append(tile)
        for tile in tiles_to_delete:
            self.all_knowledge[tile]= TileDescription(type = self.all_knowledge[tile].type, character=None, loot = None, consumable=None, effects= self.all_knowledge[tile].effects)
            del self.knowledge_age[tile]

    def see_enemy(self, tiles):
        for tile in tiles:
            if(tiles[tile].character!=None and tiles[tile].character.controller_name!="AlphaGUPB"):
                return True
        return False
    
    def get_champion(self):
        for tile in self.all_knowledge:
            if(tile == self.position):
                return self.all_knowledge[tile].character

    def position_amulet(self, enemy_position):
        if(enemy_position[0] >= self.position[0] and enemy_position[1] >= self.position[1]):
            return (enemy_position[0]-1, enemy_position[1]-1)
        
        elif(enemy_position[0] >= self.position[0] and enemy_position[1] <= self.position[1]):
            return (enemy_position[0]-1, enemy_position[1]+1)
        
        elif(enemy_position[0] <= self.position[0] and enemy_position[1] <= self.position[1]):
            return (enemy_position[0]+1, enemy_position[1]-1)
        
        elif(enemy_position[0] <= self.position[0] and enemy_position[1] >= self.position[1]):
            return (enemy_position[0]+1, enemy_position[1]+1)
    
    def should_attack(self, enemy):
        enemy = self.all_knowledge[enemy].character
        if not enemy:
            return True
        if(self.champion.health - enemy.health >2):
            return True
        if(self.champion.health<=enemy.health):
            return False
        if(self.champion.weapon.name in ['Axe', 'Sword', 'axe', 'sword', 'knife']):
            return True
        if(enemy.weapon.name in ['amulet, Amulet','knife']):
            return True
        return False

    def should_attack2(self, enemy):
        enemy = self.all_knowledge[enemy].character
        if not enemy:
            return True
        if(self.champion.health<enemy.health):
            return False
        return True
    
    def get_enemy_weapon(self, enemy):
        for tile in self.all_knowledge:
            if (tile==enemy):
                return self.all_knowledge[tile].character.weapon.name
        
    

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
        print("start")
        self.update_knowledge(knowledge.visible_tiles)
        self.alive_champions = knowledge.no_of_champions_alive
        self.position = knowledge.position
        self.positions.append(self.position)
        self.mist = self.get_mist()
        blocks = self.get_blocks(self.all_knowledge)
        self.facing= knowledge.visible_tiles[knowledge.position].character.facing
        self.weapon = knowledge.visible_tiles[knowledge.position].character.weapon
        print("pos ", self.position)
        enemies = self.get_enemies(self.all_knowledge)
        self.seen_tiles.add(self.position)
        self.attackable_tiles = attackable_tiles(self.weapon.name, self.position)
        tiles_with_potions = self.find_potion()
        weapons = self.find_weapons()
        self.champion = self.get_champion()
        arena = arenas.Arena.load(self.arena.name)

        for tile in arena.terrain:
            if(self.can_walk(tile) and (tile[0]!= self.position[0] and tile[1]!=self.position[1])):
                self.walkable_tiles.append(tile)

        if not self.menhir:
            self.menhir = self.get_menhir()

        if(len(enemies)>0):
            self.closest_enemy = self.closest_tile(self.position, enemies.keys())
        else:
            self.closest_enemy = None

            
        can_attack = can_attack_check(enemies, self.attackable_tiles)  
        print("can attack", can_attack)

        print("knowledge updated")

        if (self.closest_enemy and (self.weapon.name in ['bow_loaded', 'bow_unloaded'])):
            #print("close enemy and bow") 
            distance = self.distance(self.position, self.closest_enemy)
            if(distance < 3):
                furthest_tiles = self.furthest_tiles(self.closest_enemy, self.walkable_tiles)
                furthest_tile = self.furthest_tile_from_enemy(furthest_tiles, self.closest_enemy)
                if(furthest_tile!= self.position):
                    path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                    return self.find_move(path[1])
    
        if(can_attack and self.weapon not in ['bow_loaded', 'bow_unloaded']):
            #print('can attack')
            if(self.weapon.name =='bow_loaded'):
                return attack_enemy(self.facing, can_attack)
            if(self.should_attack2(self.closest_enemy)):
                print("should attack, attacking")
                print(self.facing)
                return attack_enemy(self.facing, can_attack)
            else:
                print("shouldnt attack")
                furthest_tiles = self.furthest_tiles(self.closest_enemy, self.walkable_tiles)
                furthest_tile = self.furthest_tile_from_enemy(furthest_tiles, self.closest_enemy)
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                if(path):
                    return self.find_move(path[1])
                else:
                    print("attacking anyway")
                    return attack_enemy(self.facing, can_attack)
                
        if(len(self.positions)>5 and len(set(self.positions[-9:])) == 1):
            print("random action")
            self.positions = []
            return random.choice(POSSIBLE_ACTIONS)
    
        if(len(self.mist)>0):
            print("mist")
            closest_mist = self.closest_tile(self.position, self.mist)
            if(self.distance(self.position, closest_mist) < 5):
                print("mist close")
                if(self.menhir): 
                    print("know menhir")
                    if(self.distance(self.position, self.menhir) > 3):
                        path = pathfinder.astar(blocks, (self.position[0], self.position[1]), self.menhir)
                        if path:
                            print("going to menhir")
                            return self.find_move(path[1])
                else:
                    print("dont know menhir")
                furthest_tiles = self.furthest_tiles(closest_mist, self.walkable_tiles)
                for tile in furthest_tiles:
                    if (tile not in self.mist and self.can_walk(tile)):
                        #print(tile)
                        path = pathfinder.astar(blocks, (self.position[0], self.position[1]), tile)
                        if (path):
                            return self.find_move(path[1])
                print("dont know where to run")
        
        if(len(tiles_with_potions)>0):
            print("potions")
            closest_potion= self.closest_tile(self.position, tiles_with_potions)
            if(closest_potion != self.position):
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_potion)
                if(path[1] not in self.mist):
                    print("going to potion")
                    return self.find_move(path[1])  


        if(self.weapon.name in ['axe', 'sword', 'knife'] and self.closest_enemy):
            if(self.should_attack(self.closest_enemy)):
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), self.closest_enemy)
                if(path[1] not in self.mist):
                    print("chasing enemy")
                    return self.find_move(path[1])
            
        if(self.weapon.name == 'bow_unloaded'):
            return characters.Action.ATTACK
        if(len(weapons)!=0 and self.weapon.name in ['knife', 'amulet', 'Amulet', 'bow_loaded', 'bow_unloaded']):
            closest_weapon = self.closest_tile(self.position, weapons.keys())
            if closest_weapon:
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_weapon)
                if(path[1]!=self.position and (path[1] not in self.mist)):
                    return self.find_move(path[1])
        
        if self.closest_enemy:
            #print(self.closest_enemy)
            enemy_weapon = self.get_enemy_weapon(self.closest_enemy)
            distance = self.distance(self.position, self.closest_enemy)
            if(distance<=3 and distance>1 and self.weapon.name !='amulet' and enemy_weapon not in ['sword', 'axe', 'bow_loaded', 'bow_unloaded']):
                print("predicting attack")
                #print(self.closest_enemy)
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), self.closest_enemy)
                if(path[1][0]<self.position[0]):
                    direction = "left"
                elif(path[1][0]>self.position[0]):
                    direction = "right"
                elif(path[1][1] > self.position[1]):
                    direction = "down"
                else:
                    direction = "up"
                return attack_enemy(self.facing, direction)
            elif(distance<8):
                print("running away")
                if len(self.walkable_tiles)>0:
                    furthest_tiles = self.furthest_tiles(self.closest_enemy, self.walkable_tiles)
                    furthest_tile = self.furthest_tile_from_enemy(furthest_tiles, self.closest_enemy)
                    if(furthest_tile!= self.position):
                        path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                        return self.find_move(path[1])
                
        if not self.menhir and self.alive_champions < 5:
            print("left")
            return controller.characters.Action.TURN_LEFT
            #print('exploring')
            not_explored = self.not_walked_tiles()
            if not not_explored:
                #print('no tiles to explore')
                pass
            closest_tile = self.closest_tile(self.position, not_explored)
            #print("going to", closest_tile)
            #print("pos", self.position)
            path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_tile)
            return self.find_move(path[1])
            #print("running :)")
            if(self.can_step_forward()):
                return controller.characters.Action.STEP_FORWARD
        print("left")
        return controller.characters.Action.TURN_LEFT


    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena = arena_description
        self.all_knowledge = {}
        self.positions = []
        self.knowledge_age = defaultdict(int)
        self.position = None
        self.champion = None
        self.facing = None
        self.menhir = None
        self.closest_enemy = None
        self.mist = []
        self.walkable_tiles = []


    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ALPHA