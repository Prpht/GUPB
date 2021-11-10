import math

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model.characters import Facing
from strategy import RandomStrategy, BB8Strategy

PI = 4.0 * math.atan(1.0)

ACTIONS_WITH_WEIGHTS = {
    characters.Action.TURN_LEFT: 0.2,
    characters.Action.TURN_RIGHT: 0.2,
    characters.Action.STEP_FORWARD: 0.5,
    characters.Action.ATTACK: 0.1,
}

TABARD_ASSIGNMENT = {
    "BB8": characters.Tabard.WHITE
}

WEAPON_SCORES = {
    "axe": 10,
    "sword": 40,
    "knife": 10,
    "amulet": 30,
    "bow_unloaded": 40,
    "bow_loaded": 40
}

ROTATIONS = {
    (Facing.UP, Facing.RIGHT): characters.Action.TURN_RIGHT,
    (Facing.UP, Facing.DOWN): characters.Action.TURN_RIGHT,
    (Facing.UP, Facing.LEFT): characters.Action.TURN_LEFT,
    (Facing.RIGHT, Facing.UP): characters.Action.TURN_LEFT,
    (Facing.RIGHT, Facing.DOWN): characters.Action.TURN_RIGHT,
    (Facing.RIGHT, Facing.LEFT): characters.Action.TURN_RIGHT,
    (Facing.DOWN, Facing.UP): characters.Action.TURN_LEFT,
    (Facing.DOWN, Facing.RIGHT): characters.Action.TURN_LEFT,
    (Facing.DOWN, Facing.LEFT): characters.Action.TURN_RIGHT,
    (Facing.LEFT, Facing.UP): characters.Action.TURN_RIGHT,
    (Facing.LEFT, Facing.RIGHT): characters.Action.TURN_RIGHT,
    (Facing.LEFT, Facing.DOWN): characters.Action.TURN_LEFT
}

MENHIR_POSITION = 25


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BB8Controller(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.position = None
        self.enemy_nearby = False
        self.visible_tiles = {}
        self.weapon = "axe"
        self.weapon_range = 1
        self.facing = None
        self.strategy = RandomStrategy()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BB8Controller):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def praise(self, score: int) -> None:
        pass

    def calculate_distance(self, other_position: coordinates.Coords) -> int:
        distance = math.sqrt((self.position.x - other_position.x) ** 2 + (self.position.y - other_position.y) ** 2)
        return int(round(distance))

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.strategy.decide(knowledge)

        """self.position = knowledge.position
        self.visible_tiles = knowledge.visible_tiles
        self.facing = self.visible_tiles[self.position].character.facing

        random_decision = random.random()
        if random_decision <= RANDOM_FACTOR:
            # return random action considering probability distribution
            return random.choices(population=list(ACTIONS_WITH_WEIGHTS.keys()),
                                  weights=list(ACTIONS_WITH_WEIGHTS.values()),
                                  k=1)[0]

        if self.__is_mist_coming():
            return self.__go_to_direction(coordinates.Coords(MENHIR_POSITION, MENHIR_POSITION))

        best_weapon_coordinates = self.__find_best_weapon()
        enemy_in_range_coordinates = self.__get_enemy_in_range_coordinates()

        if best_weapon_coordinates is not None:
            return self.__go_to_direction(best_weapon_coordinates)

        if enemy_in_range_coordinates is not None:
            desired_facing = self.__get_desired_facing(enemy_in_range_coordinates)
            if desired_facing == self.facing:
                return characters.Action.ATTACK
            else:
                return self.__rotate_to_desired_facing(enemy_in_range_coordinates)

        return random.choices(population=list(ACTIONS_WITH_WEIGHTS.keys()),
                              weights=list(ACTIONS_WITH_WEIGHTS.values()),
                              k=1)[0]"""

    def __find_best_weapon(self):
        visible_weapons = {k: v for k, v in self.visible_tiles.items() if v.loot is not None}
        best_score = 0
        best_coordinates = None

        for weapon_position in visible_weapons.keys():
            weapon_coordinates = coordinates.Coords(weapon_position[0], weapon_position[1])
            distance = self.calculate_distance(weapon_coordinates)
            weapon_name = visible_weapons[weapon_position].loot.name
            weapon_score = WEAPON_SCORES[weapon_name]
            real_score = weapon_score if weapon_score > WEAPON_SCORES[self.weapon] else 0

            score = 0.5 * real_score / (0.3 * distance)

            if score > best_score:
                best_score = score
                best_coordinates = weapon_coordinates

        return best_coordinates if best_score > 0 else None

    def __get_enemy_in_range_coordinates(self):
        visible_enemies = {k: v for k, v in self.visible_tiles.items() if
                           v.character is not None and v.character.controller_name != self.first_name}

        for enemy_position in visible_enemies.keys():
            enemy_coordinates = coordinates.Coords(enemy_position[0], enemy_position[1])
            if self.calculate_distance(enemy_coordinates) <= self.weapon_range:
                return enemy_coordinates

        return None

    def __is_mist_coming(self):
        mist_tiles = {k: v for k, v in self.visible_tiles.items() if v.effects}
        return True if mist_tiles else False

    def __get_desired_facing(self, destination_coordinates):
        r_vect = coordinates.Coords(destination_coordinates.x - self.position.x,
                                    destination_coordinates.y - self.position.y)
        angle = math.atan2(r_vect.y, r_vect.x)

        desired_facing = self.facing
        if PI / 4.0 < angle <= 3.0 * PI / 4.0:
            desired_facing = Facing.UP
        elif -1.0 * PI / 4.0 < angle <= PI / 4.0:
            desired_facing = Facing.RIGHT
        elif -3.0 * PI / 4.0 < angle <= -1.0 * PI / 4.0:
            desired_facing = Facing.DOWN
        else:
            desired_facing = Facing.LEFT

        return desired_facing

    def __rotate_to_desired_facing(self, desired_facing):
        return ROTATIONS[(self.facing, desired_facing)]

    def __go_to_direction(self, destination_coordinates):
        desired_facing = self.__get_desired_facing(destination_coordinates)

        if self.facing == desired_facing:
            return characters.Action.STEP_FORWARD
        else:
            return self.__rotate_to_desired_facing(desired_facing)

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ORANGE

    @property
    def strategy(self) -> BB8Strategy:
        return self.strategy

    @strategy.setter
    def strategy(self, new_strategy: BB8Strategy):
        self.strategy = new_strategy


POTENTIAL_CONTROLLERS = [
    BB8Controller("BB8")
]
