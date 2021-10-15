# created by Michał Kędra and Jan Proniewicz

import random

from typing import Tuple, Optional

from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model import coordinates


TABARD_ASSIGNMENT = {
    "Johnathan": characters.Tabard.BROWN,
    "Michael": characters.Tabard.VIOLET
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class EkonometronController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.starting_coords: Optional[coordinates.Coords] = None
        self.direction: Optional[Facing] = None
        self.starting_combination = [characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD,
                                     characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD,
                                     characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]
        self.run_away: Tuple[bool, int] = (False, 0)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EkonometronController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.starting_coords = None
        self.direction = None
        self.starting_combination = [characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD,
                                     characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD,
                                     characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]
        self.run_away = (False, 0)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # when bot doesn't know which direction it is facing
        if self.starting_coords is None:
            self.starting_coords = knowledge.position
            return characters.Action.STEP_FORWARD
        if self.direction is None:
            if self.starting_coords != knowledge.position:
                coords_diff = knowledge.position - self.starting_coords
                if coords_diff.x != 0:
                    if coords_diff.x > 0:
                        self.direction = Facing.RIGHT
                    else:
                        self.direction = Facing.LEFT
                elif coords_diff.y > 0:
                    self.direction = Facing.DOWN
                else:
                    self.direction = Facing.UP
            else:
                return self.starting_combination.pop(0)
        # when bot is aware which direction it is facing
        if self.run_away[0]:
            run_away_list = list(self.run_away)
            run_away_list[1] = run_away_list[1] - 1
            if run_away_list[1] == 0:
                run_away_list[0] = False
            self.run_away = tuple(run_away_list)
        # turn if there is an obstacle in front
        if self._obstacle_in_front(knowledge):
            return self._take_a_turn()
        # run away from mist or weapon cuts
        if self._negative_effect(knowledge):
            # entering "panic mode"
            if not self.run_away[0]:
                self.run_away = (True, 5)
                return self._take_a_turn()
            # if bot sees another negative effect after entering "panic mode", it can either turn again or move forward
            # (so it wouldn't be stuck in the same place... theoretically)
            else:
                return self._make_a_move(0.35, 0.65)
        # move towards weapons on the ground (unless those are knives)
        if self._weapon_in_sight(knowledge):
            # return characters.Action.STEP_FORWARD
            return self._make_a_move(0.025, 0.975)
        # attack another player in sight
        if self._enemy_in_sight(knowledge):
            # if enemy is in the area of attack
            if self._enemy_in_reach(knowledge):
                rand_gen = random.random()
                if rand_gen <= 0.95:
                    return characters.Action.ATTACK
                else:
                    return self._take_a_turn()
            else:
                return characters.Action.STEP_FORWARD
        # if there is nothing interesting going on, bot will move however it wants (but it will favor stepping forward)
        if self.run_away[0]:
            return characters.Action.STEP_FORWARD
        return self._make_a_move(0.2, 0.8)

    def _take_a_turn(self):
        """Bot chooses, whether to turn left or right"""
        rand_gen = random.random()
        if rand_gen <= 0.5:
            self.direction = self.direction.turn_left()
            return characters.Action.TURN_LEFT
        else:
            self.direction = self.direction.turn_right()
            return characters.Action.TURN_RIGHT

    def _make_a_move(self, bottom_threshold: float = 0.3, top_threshold: float = 0.7):
        """Bot turns left, right or moves forward; some 'preferences' in directions may be set"""
        rand_gen = random.random()
        if rand_gen <= bottom_threshold:
            self.direction = self.direction.turn_left()
            return characters.Action.TURN_LEFT
        elif rand_gen > top_threshold:
            self.direction = self.direction.turn_right()
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.STEP_FORWARD

    def _obstacle_in_front(self, knowledge: characters.ChampionKnowledge):
        """Bots identifies the tile right in front of it"""
        visible_tiles = knowledge.visible_tiles
        coords_in_front = knowledge.position + self.direction.value
        tile_in_front = visible_tiles[coords_in_front]
        if tile_in_front.type != "land":
            return True
        return False

    def _negative_effect(self, knowledge: characters.ChampionKnowledge):
        """Bot checks if there is any mist or weapon cutting in its surroundings"""
        visible_tiles = knowledge.visible_tiles
        # getting coordinates in square around the controller
        coords_around = []
        for i in range(-6, 7):
            for j in range(-6, 7):
                coords = knowledge.position + coordinates.Coords(i, j)
                coords_around.append(coords)
        # getting coordinates for visible tiles that are close enough
        close_coords = list(set(coords_around) & set(visible_tiles.keys()))
        # checking whether or not chosen tiles display any negative effects like mist or weapon cut
        for c in close_coords:
            current_tile = visible_tiles[c]
            effects = current_tile.effects
            for e in effects:
                if e.type == "mist" or e.type == "weaponcut":
                    return True
        return False

    def _weapon_in_sight(self, knowledge: characters.ChampionKnowledge):
        """Bot checks if it can see a potential weapon it can equip (unless it's a knife)"""
        visible_tiles = knowledge.visible_tiles
        for coords, tile in visible_tiles.items():
            if tile.loot is not None and tile.loot.name != "knife":
                return True
        return False

    def _enemy_in_sight(self, knowledge: characters.ChampionKnowledge):
        """Bot checks if it can see an enemy"""
        visible_tiles = knowledge.visible_tiles
        for coords, tile in visible_tiles.items():
            if tile.character is not None and coords != knowledge.position:
                return True
        return False

    def _enemy_in_reach(self, knowledge: characters.ChampionKnowledge):
        """Bot checks whether the enemy is in potential area of attack"""
        visible_tiles = knowledge.visible_tiles
        area_of_attack = []
        for i in range(1, 4):
            attack_coords = knowledge.position + self.direction.value * i
            area_of_attack.append(attack_coords)
            if i == 1:
                for turn in [self.direction.turn_left().value, self.direction.turn_right().value]:
                    area_of_attack.append(attack_coords + turn)
        for coords in area_of_attack:
            current_tile = visible_tiles[coords]
            if current_tile.character is not None:
                return True
        return False

    @property
    def name(self) -> str:
        return f'EkonometronController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return TABARD_ASSIGNMENT[self.first_name] if self.first_name in TABARD_ASSIGNMENT else characters.Tabard.WHITE


POTENTIAL_CONTROLLERS = [
    EkonometronController("Johnathan"),
    EkonometronController("Michael")
]
