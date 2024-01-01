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
import time

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
        self.last_hp = 8
        self.arena_knowledge = 0

        

    def find_weapons(self):
        tiles_with_weapons = {}
        for tile in self.all_knowledge:
            if(self.all_knowledge[tile].loot and self.all_knowledge[tile].loot.name not in ['bow_loaded', 'bow_unloaded','amulet']):
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
        if(tile in self.get_enemies(self.all_knowledge)):
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
        #print("updating knowledge")
        for visible_tile in visible_tiles:
            ##print(type(visible_tiles[visible_tile]))
            if(isinstance(visible_tiles[visible_tile],TileDescription)):
                self.all_knowledge[visible_tile] = copy.copy(visible_tiles[visible_tile])
                self.knowledge_age[visible_tile] = 0
            else:
                self.all_knowledge[visible_tile] = visible_tiles[visible_tile].description()
 
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
        arena = arenas.Arena.load(self.arena.name)
        if not self.arena_knowledge:
            self.update_knowledge(arena.terrain)
            self.arena_knowledge = 1
            #print("arena knowledge updated")
        self.update_knowledge(knowledge.visible_tiles)
        #print("updated 2")
        self.alive_champions = knowledge.no_of_champions_alive
        self.position = knowledge.position
        self.positions.append(self.position)
        self.mist = self.get_mist()
        self.facing= knowledge.visible_tiles[knowledge.position].character.facing
        self.weapon = knowledge.visible_tiles[knowledge.position].character.weapon
        enemies = self.get_enemies(self.all_knowledge)
        self.seen_tiles.add(self.position)
        self.attackable_tiles = attackable_tiles(self.weapon.name, self.position)
        tiles_with_potions = self.find_potion()
        #print("potions found")
        weapons = self.find_weapons()
        #print("weapons found")
        self.champion = self.get_champion()
        #print("champion got")
        self.explored_tiles = []
        
        for tile in arena.terrain:
            if(self.can_walk(tile) and (tile[0]!= self.position[0] and tile[1]!=self.position[1]) and tile not in self.mist):
                self.walkable_tiles.append(tile)
        self.explored_tiles.append(self.position)
        blocks = self.get_blocks(self.all_knowledge)
        if not self.menhir:
            self.menhir = self.get_menhir()

        if(len(enemies)>0):
            self.closest_enemy = self.closest_tile(self.position, enemies.keys())
        else:
            self.closest_enemy = None

            
        can_attack = can_attack_check(enemies, self.attackable_tiles)  
        #print("can attack ", can_attack)
        if (self.closest_enemy and (self.weapon.name in ['bow_loaded', 'bow_unloaded'])):
            
            #print("close enemy and bow") 
            distance = self.distance(self.position, self.closest_enemy)
            if(distance < 3):
                furthest_tiles = self.furthest_tiles(self.closest_enemy, self.walkable_tiles)
                #furthest_tile = self.furthest_tile_from_enemy(furthest_tiles, self.closest_enemy)\
                furthest_tile = furthest_tiles[0]
                if(furthest_tile!= self.position):
                    path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                    return self.find_move(path[1])
    
        if(can_attack and self.weapon not in ['bow_unloaded']):
            #print('can attack')
            if(self.weapon.name =='bow_loaded'):
                #print("attacking with bow")
                return attack_enemy(self.facing, can_attack)
            if(self.should_attack2(self.closest_enemy)):
                #print("attacking")
                return attack_enemy(self.facing, can_attack)
            else:
                #print("shouldnt attack")
                pass
                #if can_attack == 'right': return self.find_move((self.position[0]-1,self.position[1]))
                #if can_attack == 'left': return self.find_move((self.position[0]+1,self.position[1]))
                #if can_attack == 'up': return self.find_move((self.position[0],self.position[1]+1))
                #if can_attack == 'down': return self.find_move((self.position[0],self.position[1]-1))
                #furthest_tiles = self.furthest_tiles(self.closest_enemy, self.walkable_tiles)
                #furthest_tile = self.furthest_tile_from_enemy(furthest_tiles, self.closest_enemy)
                #path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                #if(path):
                #    #print("and running away")
                #    return self.find_move(path[1])
                #else:
                #    #print("attacking anyway")
                #    return attack_enemy(self.facing, can_attack)
                
        if(len(self.positions)>5 and len(set(self.positions[-9:])) == 1):
            self.positions = []
            #print("random move")
            return random.choice(POSSIBLE_ACTIONS)
    
        if(len(self.mist)>0):
            #print("mist")
            closest_mist = self.closest_tile(self.position, self.mist)
            if(self.distance(self.position, closest_mist) < 10):
                if(self.menhir): 
                    #print("know menhir")
                    if(self.distance(self.position, self.menhir) > 3):
                        path = pathfinder.astar(blocks, (self.position[0], self.position[1]), self.menhir)
                        if path:
                            #print("going to menhir")
                            return self.find_move(path[1])
                else:
                    for tile in self.walkable_tiles:
                        if (tile not in self.mist):
                            path = pathfinder.astar(blocks, (self.position[0], self.position[1]), tile)
                            if(path):
                                #print("no menhir, running away")
                                return self.find_move(path[1])
                        
               # furthest_tiles = self.furthest_tiles(closest_mist, self.walkable_tiles)
               # for tile in furthest_tiles:
               #     if (tile not in self.mist and self.can_walk(tile)):
               #         path = pathfinder.astar(blocks, (self.position[0], self.position[1]), tile)
               #         if (path):
               #             #print("no menhir, running away")
               #             return self.find_move(path[1])
        
        if(len(tiles_with_potions)>0):
            closest_potion= self.closest_tile(self.position, tiles_with_potions)
            if(closest_potion != self.position):
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_potion)
                if(path[1] not in self.mist):
                    #print("going to potion")
                    return self.find_move(path[1])  


        if(self.weapon.name in ['axe', 'sword', 'knife'] and self.closest_enemy):
            if(self.should_attack(self.closest_enemy)):
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), self.closest_enemy)
                if(path[1] not in self.mist):
                    #print("chasing enemy")
                    return self.find_move(path[1])
            
        if(self.weapon.name == 'bow_unloaded'):
            return characters.Action.ATTACK
        if(len(weapons)!=0 and self.weapon.name in ['knife', 'amulet', 'Amulet', 'bow_loaded', 'bow_unloaded']):
            closest_weapon = self.closest_tile(self.position, weapons.keys())
            #print("closest weapon", closest_weapon)
            if closest_weapon:
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_weapon)
                if(path):
                    if(path[1]!=self.position and (path[1] not in self.mist) and len(path)<20):
                        #print("going to weapon")
                        return self.find_move(path[1])
                    else:
                        
                        #print("weapon too far away")
                        pass
        
        if self.closest_enemy:
            enemy_weapon = self.get_enemy_weapon(self.closest_enemy)
            distance = self.distance(self.position, self.closest_enemy)
            if(distance<=3 and distance>1 and self.weapon.name !='amulet' and enemy_weapon not in ['sword', 'axe', 'bow_loaded', 'bow_unloaded']):
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), self.closest_enemy)
                if(path[1][0]<self.position[0]):
                    direction = "left"
                elif(path[1][0]>self.position[0]):
                    direction = "right"
                elif(path[1][1] > self.position[1]):
                    direction = "down"
                else:
                    direction = "up"
                    #print("predicting attack")
                return attack_enemy(self.facing, direction)
            elif(distance<8):
                if len(self.walkable_tiles)>0:
                    furthest_tiles = self.furthest_tiles(self.closest_enemy, self.walkable_tiles)
                    furthest_tile = self.furthest_tile_from_enemy(furthest_tiles, self.closest_enemy)
                    if(furthest_tile!= self.position):
                        path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                        #print("running away")
                        return self.find_move(path[1])
                    
        if(self.champion.health<self.last_hp):
            self.last_hp = self.champion.health
            #print("someone is attacking")
            if(self.can_step_forward):
                #print("running away forward")
                return controller.characters.Action.STEP_FORWARD
            else:
                #print("running away backward")
                return controller.characters.Action.STEP_BACKWARD
                
        if not self.menhir and self.alive_champions < 5:
            random_tile = random.choice(self.walkable_tiles)
            if random_tile not in self.explored_tiles:
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), random_tile)
                #print("exploring")
                return self.find_move(path[1])
        

            return controller.characters.Action.TURN_LEFT
            ##print('exploring')
            not_explored = self.not_walked_tiles()
            if not not_explored:
                ##print('no tiles to explore')
                pass
            closest_tile = self.closest_tile(self.position, not_explored)
            ##print("going to", closest_tile)
            ##print("pos", self.position)
            path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_tile)
            return self.find_move(path[1])
            ##print("running :)")
            if(self.can_step_forward()):
                return controller.characters.Action.STEP_FORWARD
        #print("left")
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
        self.explored_tiles = []
        self.arena_knowledge = 0


    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ALPHA