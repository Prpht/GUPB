from gupb.controller.ancymon.environment import Environment
from gupb.controller.ancymon.strategies.path_finder import Path_Finder
from gupb.controller.ancymon.strategies.decision_enum import HUNTER_DECISION
from gupb.model import characters
from gupb.model.coordinates import Coords

class Hunter:
    def __init__(self, environment: Environment):
        self.environment: Environment = environment
        self.path_finder: Path_Finder = None

        self.next_target = None
        self.next_target_coord: Coords = None

        self.next_move: characters.Action = None
        self.path: list[Coords] = None

    def decide(self, path_finder: Path_Finder):
        self.path_finder = path_finder
        self.next_move = None
        self.path = None

        potential_enemies = self.neerest_enemy_list()

        if len(potential_enemies) > 0:
            if self.can_attack():
                self.next_move = characters.Action.ATTACK
                return HUNTER_DECISION.ATTACK

            for enemy in potential_enemies:
                self.next_target_coord = enemy
                self.next_target = self.environment.discovered_map.get(enemy).character
                cord_position_to_atack = self.find_coord_to_attack_spot()
                self.next_move, self.path = self.path_finder.calculate_next_move(cord_position_to_atack)
                if self.next_move:
                    return HUNTER_DECISION.CHASE

        return HUNTER_DECISION.NO_ENEMY

    def is_target_on_same_position(self):
        if self.next_target and self.next_target_coord:
            enemy_field = self.environment.discovered_map.get(self.next_target_coord)
            if enemy_field and enemy_field.character:
                return
        self.next_target = None
        self.next_target_coord: Coords = None

    def neerest_enemy_list(self) -> list[Coords]:
        enemy_coords_list = []

        for coords, description in self.environment.discovered_map.items():
            coords = Coords(coords[0], coords[1])
            if description.character and description.character.controller_name != self.environment.champion.controller_name:
                enemy_coords_list.append(coords)
        return sorted(enemy_coords_list, key=lambda x: self.path_finder.calculate_path_length(x))

    def is_enemy_neer(self, size_of_searched_area: int = 3):
        for x in range(-size_of_searched_area, size_of_searched_area + 1):
            for y in range(-size_of_searched_area, size_of_searched_area + 1):
                field = self.environment.discovered_map.get(self.environment.position + Coords(x, y))
                if field != None and field.character != None and field.character.controller_name != self.environment.champion.controller_name:
                    self.next_target = field.character
                    self.next_target_coord = Coords(x, y) + self.environment.position
                    return True
        self.next_target = None
        self.next_target_coord = None
        return False

    def is_character_on_visible_field(self, further_position: Coords) -> bool:
        return self.environment.visible_map.get(further_position) and self.environment.visible_map.get(
            further_position).character

    def can_attack(self) -> bool:
        position = self.environment.position
        further_position = position + self.environment.champion.facing.value

        if self.environment.weapon.name == 'knife':
            if self.is_character_on_visible_field(further_position):
                return True
            return False

        if self.environment.weapon.name == 'sword':
            for i in range(3):
                if self.is_character_on_visible_field(further_position):
                    return True
                further_position += self.environment.champion.facing.value
            return False

        if self.environment.weapon.name == 'bow_loaded' or self.environment.weapon.name == 'bow_unloaded':
            while (self.environment.visible_map.get(further_position)):
                if self.environment.visible_map.get(further_position).character:
                    return True
                further_position += self.environment.champion.facing.value
            return False

        if self.environment.weapon.name == 'amulet':
            for direction in [Coords(1, 1), Coords(-1, -1), Coords(1, -1), Coords(-1, 1)]:
                further_position = position
                for i in range(2):
                    further_position += direction
                    if self.is_character_on_visible_field(further_position):
                        return True
            return False

        if self.environment.weapon.name == 'axe':
            if (
                    (further_position.x != position.x and (
                            self.environment.visible_map[further_position].character or
                            self.environment.visible_map[
                                Coords(further_position.x, further_position.y + 1)].character or
                            self.environment.visible_map[Coords(further_position.x, further_position.y - 1)].character
                    )) or
                    (further_position.y != position.y and (
                            self.environment.visible_map[further_position].character or
                            self.environment.visible_map[
                                Coords(further_position.x + 1, further_position.y)].character or
                            self.environment.visible_map[Coords(further_position.x - 1, further_position.y)].character
                    ))
            ):
                return True
            return False

        return False

    def find_coord_to_attack_spot(self):

        new_attack_spot_dist = float('inf')
        new_attack_spot = self.next_target_coord

        if self.environment.weapon.name == 'knife':
            return self.next_target_coord

        # elif self.environment.weapon.name == 'sword':
        #     for direction in [Coords(0, 1), Coords(0, -1), Coords(1, 0), Coords(-1, 0)]:
        #         further_position = self.next_target_coord
        #         for i in range(2):
        #             further_position += direction
        #             spot = self.environment.visible_map.get(further_position)
        #             if spot and spot.type == 'land':
        #                 spot_dist = self.path_finder.calculate_path_length(further_position)
        #                 if (new_attack_spot == None or spot_dist < new_attack_spot_dist):
        #                     new_attack_spot_dist = spot_dist
        #                     new_attack_spot = further_position

        elif self.environment.weapon.name == 'amulet':
            for direction in [Coords(1, 1), Coords(1, -1), Coords(-1, 1), Coords(-1, -1)]:
                further_position = self.next_target_coord
                for i in range(2):
                    further_position += direction
                    spot = self.environment.discovered_map.get(further_position)
                    if spot and spot.type == 'land':
                        spot_dist = self.path_finder.calculate_path_length(further_position)
                        if (new_attack_spot == None or spot_dist < new_attack_spot_dist):
                            new_attack_spot_dist = spot_dist
                            new_attack_spot = further_position

        elif self.environment.weapon.name == 'axe':
            for direction in [Coords(0, 1), Coords(0, -1)]:
                for direction_2 in [Coords(0, 0), Coords(1, 0), Coords(-1, 0)]:
                    further_position = self.next_target_coord + direction + direction_2
                    spot = self.environment.discovered_map.get(further_position)
                    if spot and spot.type == 'land':
                        spot_dist = self.path_finder.calculate_path_length(further_position)
                        if new_attack_spot is None or spot_dist < new_attack_spot_dist:
                            new_attack_spot_dist = spot_dist
                            new_attack_spot = further_position

            for direction in [Coords(1, 0), Coords(-1, 0)]:
                for direction_2 in [Coords(0, 0), Coords(0, 1), Coords(0, -1)]:
                    further_position = self.next_target_coord + direction + direction_2
                    spot = self.environment.discovered_map.get(further_position)
                    if spot and spot.type == 'land':
                        spot_dist = self.path_finder.calculate_path_length(further_position)
                        if new_attack_spot is None or spot_dist < new_attack_spot_dist:
                            new_attack_spot_dist = spot_dist
                            new_attack_spot = further_position

        # print(new_attack_spot)
        return new_attack_spot
