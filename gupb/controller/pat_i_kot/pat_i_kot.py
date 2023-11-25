import random
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import arenas
from gupb.controller.pat_i_kot import analyze_map
from gupb.controller.pat_i_kot import analyze_weapon

WEAPON_WITH_WEIGHTS = {
    'knife': 2,
    'amulet': 3,
    'sword': 5,
    'bow_unloaded': 1,
    'bow_loaded': 1,
    'axe': 3
}

ACTIONS_WITH_WEIGHTS = {
    characters.Action.TURN_LEFT: 0.4,
    characters.Action.TURN_RIGHT: 0.4,
    characters.Action.STEP_FORWARD: 0.2
}

class PatIKotController:
    def __init__(self, first_name: str):
        self.dangerous_tiles = None
        self.path = None
        self.arena = None
        self.better_weapon_coords = None
        self.better_weapon = None
        self.weapon = None
        self.possible_menhir_coords = None
        self.menhir_coords = None
        self.nearest_potion_coords = None
        self.gps = None
        self.first_name: str = first_name
        self.time_before_actions = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PatIKotController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_coords = None
        self.possible_menhir_coords = []
        self.weapon = 'knife'
        self.better_weapon = 'knife'
        self.better_weapon_coords = None
        self.nearest_potion_coords = None
        self.gps = analyze_map.PathFinder(arena_description)
        self.arena = arenas.Arena.load(arena_description.name)
        self.path = []
        self.dangerous_tiles = []
        self.time_before_actions = 0

        for coords in self.arena.terrain.keys():
            if self.arena.terrain[coords].passable:
                self.possible_menhir_coords.append(coords)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles
        self_description = visible_tiles[position].character
        self.weapon = self_description.weapon.name
        self.dangerous_tiles = []


        self.time_before_actions +=1

        if len(self.path) != 0:
            if position == coordinates.Coords(*self.path[0]):
                self.path.pop(0)

        if self.nearest_potion_coords is not None and self.nearest_potion_coords in visible_tiles.keys():
            if visible_tiles[self.nearest_potion_coords].consumable is None:
                self.nearest_potion_coords = None

        if self.nearest_potion_coords is None:
            current_dist_to_potion = 3500
        else:
            current_dist_to_potion = len(self.gps.find_path(position, coordinates.Coords(self.nearest_potion_coords[0],
                                                                                     self.nearest_potion_coords[1])))


        for visible_position in visible_tiles.keys():

            if self.menhir_coords is None and visible_tiles[visible_position].type == 'menhir':
                self.menhir_coords = visible_position

            if visible_tiles[visible_position].loot is not None:
                other_weapon = visible_tiles[visible_position].loot.name

                if WEAPON_WITH_WEIGHTS[other_weapon] > WEAPON_WITH_WEIGHTS[self.weapon]:

                    if WEAPON_WITH_WEIGHTS[other_weapon] > WEAPON_WITH_WEIGHTS[self.better_weapon]:

                        self.better_weapon_coords = visible_position
                        self.better_weapon = other_weapon

            if visible_tiles[visible_position].character is not None and visible_position != position:
                enemy = visible_tiles[visible_position].character
                enemy_weapon = enemy.weapon.name
                danger_zone = analyze_weapon.get_weapon(self.arena, visible_position, enemy.facing, enemy_weapon)
                self.dangerous_tiles += danger_zone

            if visible_tiles[visible_position].consumable is not None and visible_position not in self.dangerous_tiles:
                new_dist_to_potion = len(self.gps.find_path(position, visible_position))
                if new_dist_to_potion < min(5, current_dist_to_potion):
                    self.nearest_potion_coords = visible_position


        self.possible_menhir_coords = [coord for coord in self.possible_menhir_coords if
                                       coord not in visible_tiles.keys()]

        if self.better_weapon_coords == position:
            self.better_weapon_coords = None

        if self_description is not None:
            facing = self_description.facing
            weapon_tile = analyze_weapon.get_weapon(self.arena, position, facing, self.weapon)
            if self.weapon == 'bow_unloaded':
                return characters.Action.ATTACK


            for tile_coords in weapon_tile:
                if tile_coords in visible_tiles.keys():
                    if visible_tiles[tile_coords].character is not None:
                        return characters.Action.ATTACK


            if position in self.dangerous_tiles:
                if position + facing.value not in self.dangerous_tiles and self.arena.terrain[
                    position + facing.value].passable:
                    return characters.Action.STEP_FORWARD
                safe_spot = analyze_map.find_safe_spot(position, self.dangerous_tiles, self.arena)
                if safe_spot is not None:
                    self.path = self.gps.find_path(position, safe_spot)
                    next_action = analyze_map.next_move(position, coordinates.Coords(*self.path[0]), facing)
                    return next_action

            if self.nearest_potion_coords is not None:
                if len(self.path) == 0 or self.path[-1] != self.nearest_potion_coords:
                    path_to_potion = self.gps.find_path(position, coordinates.Coords(self.nearest_potion_coords[0],
                                                                                         self.nearest_potion_coords[1]))
                    self.path = path_to_potion

            if visible_tiles[position].type == "menhir" and self.weapon != "bow_loaded" and self.nearest_potion_coords is None:
                return random.choice([characters.Action.TURN_RIGHT,characters.Action.STEP_BACKWARD])


            if len(self.path) == 0:

                if self.menhir_coords is not None and self.weapon != "knife" and self.time_before_actions>30:
                    path_to_menhir = self.gps.find_path(position, coordinates.Coords(self.menhir_coords[0],
                                                                                     self.menhir_coords[1]))
                    self.path = path_to_menhir

                elif self.better_weapon_coords is not None:
                    path_to_weapon = self.gps.find_path(position, coordinates.Coords(self.better_weapon_coords[0],
                                                                                     self.better_weapon_coords[1]))
                    self.path = path_to_weapon

                else:
                    random_destination = random.choice(self.possible_menhir_coords)
                    path_to_destination = self.gps.find_path(position, random_destination)
                    self.path = path_to_destination

            next_action = analyze_map.next_move(position, coordinates.Coords(*self.path[0]), facing)


            if next_action == characters.Action.STEP_FORWARD:
                if (position + facing.value) in self.dangerous_tiles \
                        or visible_tiles[(position + facing.value)].character is not None:
                    safe_spot = analyze_map.find_safe_spot(position, self.dangerous_tiles, self.arena)
                    if safe_spot is not None:
                        self.path = self.gps.find_path(position, safe_spot)
                        next_action = analyze_map.next_move(position, coordinates.Coords(*self.path[0]), facing)
            return next_action

            # after some strategies delete this fragment
            # type_of_tile = tile_in_front.type
            # if type_of_tile in ["sea", "wall"]:
            #     return random.choice([characters.Action.TURN_RIGHT, characters.Action.TURN_LEFT])
            # elif type_of_tile == "menhir":
            #     return characters.Action.STEP_FORWARD
        return random.choices(population=list(ACTIONS_WITH_WEIGHTS.keys()),
                              weights=list(ACTIONS_WITH_WEIGHTS.values()),
                              k=1)[0]

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PIKACHU

    def praise(self, score: int) -> None:
        pass
