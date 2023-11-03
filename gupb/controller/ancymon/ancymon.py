import random

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.coordinates import Coords
from gupb.controller.ancymon.environment import Environment
from gupb.controller.ancymon.strategies.explore import Explore
from gupb.controller.ancymon.strategies.hunter import Hunter
from gupb.controller.ancymon.strategies.path_finder import Path_Finder
from gupb.model.weapons import Knife, Sword, Bow, Amulet, Axe

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

class AncymonController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.environment: Environment = Environment()
        self.path_finder: Path_Finder = Path_Finder(self.environment)
        self.explore: Explore = Explore(self.environment, self.path_finder)
        self.hunter: Hunter = Hunter(self.environment, self.path_finder)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AncymonController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.environment.update_environment(knowledge)

        decision = None

        try:
            decision = self.hunter.decide()
            if decision != None:
                return decision
        except Exception as e:
            print(f"An exception occurred in Hunter strategy: {e}")

        try:
            decision = self.explore.decide()
        except Exception as e:
            print(f"An exception occurred in Explore strategy: {e}")

        #After providing hunter decider nothing below should be requierd

        try:
            new_position = self.environment.position + self.environment.discovered_map[
                self.environment.position].character.facing.value
            if self.collect_loot(new_position):
                return POSSIBLE_ACTIONS[2]
            # if self.can_attack(knowledge):
            #     return POSSIBLE_ACTIONS[3]
            
            if self.is_menhir_neer():
                return random.choices(
                    population=POSSIBLE_ACTIONS[:3], weights=(20, 20, 60), k=1
                )[0]
        except Exception as e:
            print(f"An exception occurred: {e}")

        return decision

    def is_menhir_neer(self):
        if self.environment.menhir != None:
            margin = self.environment.enemies_left - 2
            # margin = 4
            if len(self.environment.discovered_map[self.environment.position].effects) > 0:
                margin = 0
            return (abs(self.environment.menhir[0] - self.environment.position.x) < margin and
                    abs(self.environment.menhir[1] - self.environment.position.y) < margin)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.environment = Environment()
        self.path_finder.environment = self.environment
        self.explore.environment = self.environment
        self.hunter.environment = self.environment

    @property
    def name(self) -> str:
        return f"{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ANCYMON

    def should_attack(self, new_position):
        if self.environment.discovered_map[new_position].character:
            if (
                    self.environment.discovered_map[new_position].character.health
                    <= self.environment.discovered_map[self.environment.position].character.health
            ):
                return True
            # opponent is not facing us
            elif (
                    new_position + self.environment.discovered_map[new_position].character.facing.value
                    == self.environment.position
            ):
                return False

        return False

    def collect_loot(self, new_position):
        return (
            self.environment.discovered_map[new_position].loot and self.environment.weapon == Knife
        ) or self.environment.discovered_map[new_position].consumable
    
    def can_attack(self, knowledge: characters.ChampionKnowledge):
        position=self.environment.position
        new_position = position + self.environment.discovered_map[self.environment.position].character.facing.value

        # check if we see any enemy (no point to attack if there are no visible enemies)
        see_enemy = False
        for coords in knowledge.visible_tiles:
            if coords==position:
                continue
            if (knowledge.visible_tiles[coords].character or knowledge.visible_tiles[Coords(coords[0], coords[1])].character):
                see_enemy = True
        
        if not see_enemy:
            return False

        if self.environment.weapon.name == 'knife':
            if self.environment.discovered_map[new_position].character:
                return True
            return False
            
        if self.environment.weapon.name=='sword':
            two_positions_further = new_position + self.environment.discovered_map[self.environment.position].character.facing.value
            three_positions_further = two_positions_further + self.environment.discovered_map[self.environment.position].character.facing.value
            # won't it try to hit through walls?
            # if self.environment.discovered_map[new_position].character or self.environment.discovered_map[two_positions_further].character or self.environment.discovered_map[three_positions_further].character:
            if knowledge.visible_tiles[new_position].character or knowledge.visible_tiles[two_positions_further].character or knowledge.visible_tiles[three_positions_further].character:
                return True
            return False

        #TODO bow needs two actions to fire; right now bot with bow does nothing
        if self.environment.weapon.name=='bow':
            fields_in_line = []
            pos=position
            # calculating how many tiles are there in line
            if new_position.y==position.y: 
                if new_position.x>position.x:
                    steps=self.environment.map_known_len-position.x
                else:
                    steps=position.x-1
            else:
                if new_position.y>position.y:
                    steps=self.environment.map_known_len-position.y
                else:
                    steps=position.y-1
            for _ in range(steps):
                next_pos=pos+self.environment.discovered_map[pos].character.facing.value
                if next_pos in knowledge.visible_tiles:
                    fields_in_line.append(next_pos)
                    pos=next_pos
                else:
                    break
            if len(fields_in_line)>0:
                return True
            
            return False
            
        if self.environment.weapon.name=='amulet':
            positions_to_check = [
                Coords(position.x - 1, position.y + 1),
                Coords(position.x + 1, position.y + 1),
                Coords(position.x - 1, position.y - 1),
                Coords(position.x + 1, position.y - 1),
                Coords(position.x - 2, position.y + 2),
                Coords(position.x + 2, position.y + 2),
                Coords(position.x - 2, position.y - 2),
                Coords(position.x + 2, position.y - 2),
                ]

            for pos in positions_to_check:
                # is it correct condition or should be visible_tiles[pos].caracter?
                # if self.environment.discovered_map[pos].character:
                if pos in knowledge.visible_tiles and knowledge.visible_tiles[pos].character:
                    return True
            return False

        if self.environment.weapon.name=='axe':
        #     if (
        #     (new_position.x != position.x and (
        #         self.environment.discovered_map[new_position].character or
        #         self.environment.discovered_map[Coords(new_position.x, new_position.y + 1)].character or
        #         self.environment.discovered_map[Coords(new_position.x, new_position.y - 1)].character
        #     )) or
        #     (new_position.y != position.y and (
        #         self.environment.discovered_map[new_position].character or
        #         self.environment.discovered_map[Coords(new_position.x + 1, new_position.y)].character or
        #         self.environment.discovered_map[Coords(new_position.x - 1, new_position.y)].character
        #     ))
        # ):
            if (
            (new_position.x != position.x and (
                knowledge.visible_tiles[new_position].character or
                knowledge.visible_tiles[Coords(new_position.x, new_position.y + 1)].character or
                knowledge.visible_tiles[Coords(new_position.x, new_position.y - 1)].character
            )) or
            (new_position.y != position.y and (
                knowledge.visible_tiles[new_position].character or
                knowledge.visible_tiles[Coords(new_position.x + 1, new_position.y)].character or
                knowledge.visible_tiles[Coords(new_position.x - 1, new_position.y)].character
            ))
            ):
                return True
            
            return False
        
        return False
                
