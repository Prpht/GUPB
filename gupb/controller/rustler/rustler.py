import random
from typing import Dict, List, Set

import numpy as np

from gupb import controller
from gupb.controller.rustler import utils
from gupb.controller.rustler.goal import Goal
from gupb.controller.rustler.pathfinder import PathFinder
from gupb.controller.rustler.weapon_util import get_attack_positions
from gupb.model import arenas, characters, coordinates, tiles, weapons

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


class Hyperparams:
    def __init__(self, **kwargs):
        # Default values
        self.better_weapons: List[str] = kwargs.get(
            "better_weapons", ["amulet", "axe", "sword"]
        )
        self.blacklisted_letters: List[str] = kwargs.get(
            "blacklisted_letters", ["B", "C"]
        )
        self.aggression_turn_dst: int = kwargs.get("aggression_turn_dst", 3)
        self.special_hidden: coordinates.Coords | None = (
            coordinates.Coords(*kwargs["special_hidden_spot"])
            if kwargs.get("special_hidden_spot")
            else None
        )

        # Boolean settings
        self.menhir_ignore: bool = kwargs.get("menhir_ignore", False)
        self.mist_ignore: bool = kwargs.get("mist_ignore", False)
        self.ignore_possible_attack_opportunity: bool = kwargs.get(
            "ignore_possible_attack_opportunity", False
        )
        self.closest_hidden: bool = kwargs.get("closest_hidden", True)
        self.disable_hidden_spots: bool = kwargs.get("disable_hidden_spots", False)
        self.go_to_weapon_first: bool = kwargs.get("go_to_weapon_first", True)
        self.ignore_weapon: bool = kwargs.get("ignore_weapon", False)
        self.true_random: bool = kwargs.get("true_random", False)
        self.ignore_potion: bool = kwargs.get("ignore_potion", False)
        self.bow_disables_aggro: bool = kwargs.get("bow_disables_aggro", True)
        self.explore: bool = kwargs.get(
            "explore", False
        )  # randomize hidden spot when reached
        self.attack_when_in_path: bool = kwargs.get("attack_when_in_path", True)
        self.auto_load_bow: bool = kwargs.get("auto_load_bow", False)
        self.mist_escape_limit: int = kwargs.get("mist_escape_limit", 5)


class ThompsonSampling:
    REWARDS = [
        0,
        1,
        2,
        3,
        4,
        5,
        7,
        9,
        12,
        17,
        23,
        30,
        41,
        55,
        74,
        99,
        133,
        178,
        239,
        320,
        429,
        575,
        770,
        1031,
        1381,
        1850,
        2479,
        3320,
        4447,
        5956,
        7977,
        10685,
    ]

    def __init__(self, arms: Dict[str, Hyperparams], no_players: int):
        self.arms = arms
        self.successes = {arm: 1 for arm in arms}
        self.failures = {arm: 1 for arm in arms}
        self.max_reward = self.REWARDS[no_players]

    def select_arm(self) -> tuple[str, Hyperparams]:
        # Sample from Beta distribution for each arm and pick the one with the highest value
        sampled_values = {
            arm: np.random.beta(self.successes[arm], self.failures[arm])
            for arm in self.arms.keys()
        }
        chosen_key = max(sampled_values, key=sampled_values.get)
        return chosen_key, self.arms[chosen_key]

    def update(self, chosen_name: str, reward: int):
        if 0 <= reward <= self.max_reward:
            self.successes[chosen_name] += reward
            self.failures[chosen_name] += self.max_reward - reward

    def __str__(self):
        str = ""
        for key in self.arms.keys():
            str += f"{key}: {self.successes[key]} {self.failures[key]} \n"
        return str


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Rustler(controller.Controller):
    """
    Oxidized, Blazingly Fast, Overengineered for Survival.
    """

    def __init__(self, first_name: str = "Rustler", **kwargs):
        self.first_name: str = first_name
        HIDING_SPOTS = [(10, 10), (22, 2), (22, 14), (6, 22), (5, 5), (14, 4)]
        self.HIDING_SPOTS: List[coordinates.Coords] = [
            coordinates.Coords(x, y) for x, y in HIDING_SPOTS
        ]

        self.path_finder: PathFinder = PathFinder()

        self.menhir: coordinates.Coords | None = None
        self.mist: coordinates.Coords | None = None
        self.facing: characters.Facing | None = None
        self.weapon: weapons.WeaponDescription | None = None
        self.prev_weapon: weapons.WeaponDescription | None = None
        self.previous_position: coordinates.Coords | None = None
        self.curr_targets_set: Set[Goal] = set()
        self.charges: int = 5
        self.in_fire: bool = False
        self.target_facings: List[str] = []
        self.spawned: bool = False
        self.thompson: ThompsonSampling | None = None
        self.curr_thompson_name: str = ""
        self.curr_params: Hyperparams | None = None
        self.t: int = 0
        self.misted_set: Set[coordinates.Coords] = set()

        if not kwargs:
            pass
            # Thompson Sampling algo will be run later bc we need to know no_players
        else:
            self.curr_params = Hyperparams(**kwargs)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Rustler):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def init_thompson_sampling(self, no_players: int):
        arms = {
            "FIRE": {
                "blacklisted_letters": ["A", "M", "S", "B"],
                "aggression_turn_dst": 100,
                "explore": False,
            },
            "KILER_HUNTER": {
                "blacklisted_letters": ["C", "B"],
                "aggression_turn_dst": 100,
                "explore": True,
            },
            "KILER_BEST": {
                "special_hidden": (22, 14),
                "blacklisted_letters": ["C", "B"],
                "aggression_turn_dst": 100,
                "explore": False,
            },
            "KILER_CENTER": {
                "special_hidden": (10, 10),
                "blacklisted_letters": ["C", "B"],
                "aggression_turn_dst": 100,
                "explore": False,
            },
            "NO_HIDE": {
                "disable_hidden_spots": True,
                "blacklisted_letters": ["C", "B"],
                "aggression_turn_dst": 100,
            },
            "ARCHER_AGRESS": {
                "better_weapons": [
                    "loaded_bow",
                    "unloaded_bow",
                    "amulet",
                    "axe",
                    "sword",
                ],
                "blacklisted_letters": ["M", "A", "S", "C"],
                "auto_load_bow": True,
                "bow_disables_aggro": False,
            },
            "ARCHER": {
                "better_weapons": [
                    "loaded_bow",
                    "unloaded_bow",
                    "amulet",
                    "axe",
                    "sword",
                ],
                "blacklisted_letters": ["M", "A", "S", "C"],
                "auto_load_bow": True,
                "bow_disables_aggro": False,
            },
            "PASSIVE": {
                "go_to_weapon_first": False,
                "aggression_turn_dst": 0,
                "menhir_ignore": True,
            },
            "CAMPER": {
                "special_hidden": (22, 3),
                "ignore_weapon": True,
                "go_to_weapon_first": False,
                "aggression_turn_dst": 1,
            },
            "CAMPER_NO_MENHIR": {
                "special_hidden": (22, 3),
                "ignore_weapon": True,
                "go_to_weapon_first": False,
                "aggression_turn_dst": 1,
                "menhir_ignore": True,
            },
            "NORMAL": {"blacklisted_letters": ["B", "C"], "aggression_turn_dst": 1},
            "NORMAL_NO_MENHIR": {
                "blacklisted_letters": ["B", "C"],
                "aggression_turn_dst": 1,
                "menhir_ignore": True,
            },
            "NORMAL_NO_WEAPON_CORNER": {
                "special_hidden": (4, 4),
                "better_weapons": ["sword", "amulet"],
                "go_to_weapon_first": False,
                "aggression_turn_dst": 3,
            },
            "NO_BLACKLIST": {"blacklisted_letters": [], "aggression_turn_dst": 1},
            "SWORD": {
                "blacklisted_letters": ["B", "A", "M", "C"],
                "better_weapons": ["sword", "amulet", "axe"],
                "aggression_turn_dst": 100,
                "explore": True,
                "menhir_ignore": False,
            },
            "AXE": {
                "blacklisted_letters": ["B", "M", "S", "C"],
                "better_weapons": ["axe", "amulet", "sword"],
                "aggression_turn_dst": 100,
                "explore": True,
                "menhir_ignore": False,
            },
        }
        arms = {key: Hyperparams(**value) for (key, value) in arms.items()}
        self.thompson = ThompsonSampling(arms, no_players)
        self.curr_thompson_name, self.curr_params = self.thompson.select_arm()

    def go_to_hidden_spot(self, knowledge: characters.ChampionKnowledge):
        dst, cords = min(
            [
                (utils.norm(spot - knowledge.position), spot)
                for spot in self.HIDING_SPOTS
            ],
            key=lambda x: x[0],
        )
        self.curr_targets_set.add(Goal("hide", 1000, cords, self.curr_params.explore))

    def initial_find_weapon(self, knowledge):
        self.weapon = knowledge.visible_tiles[knowledge.position].character.weapon
        if self.weapon.name == "knife":
            weapons_list = self.path_finder.letters_position(
                knowledge.position.x,
                knowledge.position.y,
                self.curr_params.blacklisted_letters,
            )
            self.curr_targets_set.add(
                Goal(
                    "weapon",
                    1,
                    coordinates.Coords(weapons_list[0][0], weapons_list[0][1]),
                    True,
                )
            )

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.t += 1
            if self.curr_params is None:
                self.init_thompson_sampling(knowledge.no_of_champions_alive)
            if self.curr_params.true_random:
                return random.choice(POSSIBLE_ACTIONS)

            # hidden spot init
            if not self.spawned:
                if self.curr_params.go_to_weapon_first:
                    self.initial_find_weapon(knowledge)
                self.spawned = True
                if not self.curr_params.disable_hidden_spots:
                    if self.curr_params.special_hidden:
                        self.curr_targets_set.add(
                            Goal(
                                "hide",
                                1000,
                                self.curr_params.special_hidden,
                                self.curr_params.explore,
                            )
                        )
                    else:
                        self.go_to_hidden_spot(knowledge)

            curr_tile = knowledge.visible_tiles[knowledge.position]

            self.facing = curr_tile.character.facing
            if (
                not self.curr_params.ignore_weapon
                and self.prev_weapon is not None
                and self.prev_weapon.name != "knife"
                and self.prev_weapon.name != self.weapon.name
                and self.weapon.name not in self.curr_params.better_weapons
                and self.prev_weapon.name in self.curr_params.better_weapons
            ):
                self.curr_targets_set.add(
                    Goal("weapon", -1001, self.previous_position, True, None)
                )
                # ^ above if adds weapon goal when we accidently swapped good weapon for a bad one and moved on
                # (remembers dropping it even if its not in knowledge.visible_tiles)

            self.prev_weapon = self.weapon
            self.previous_position = knowledge.position
            self.weapon = knowledge.visible_tiles[knowledge.position].character.weapon

            # scroll and bow
            if self.weapon.name != "scroll":
                self.charges = 5
            if self.weapon.name == "scroll" and self.charges == 0:
                self.agress_turn_on_dst = 0
            if self.curr_params.bow_disables_aggro and self.weapon == "bow":
                self.agress_turn_on_dst = 0
            else:
                self.agress_turn_on_dst = self.curr_params.aggression_turn_dst
            if self.curr_params.auto_load_bow and self.weapon.name == "bow_unloaded":
                return characters.Action.ATTACK
            # menhir
            if self.menhir is None and not self.curr_params.menhir_ignore:
                for key, tile in knowledge.visible_tiles.items():
                    if tile.type == "menhir":
                        self.menhir = coordinates.Coords(key[0], key[1])
                        if self.mist is not None:
                            self.curr_targets_set.add(
                                Goal("menhir", -1000, self.menhir, False, None, 2)
                            )

            # mist
            if not self.curr_params.mist_ignore:
                for key, tile in knowledge.visible_tiles.items():
                    for effect in tile.effects:
                        if effect.type == "mist":
                            self.misted_set.add(coordinates.Coords(key[0], key[1]))
                            self.mist = True
                            if self.menhir and not self.curr_params.menhir_ignore:
                                self.curr_targets_set.add(
                                    Goal("menhir", -1000, self.menhir, False, None, 2)
                                )

            if (
                not self.curr_params.mist_ignore
                and self.mist
                and len(
                    [
                        tile
                        for tile, tile_description in knowledge.visible_tiles.items()
                        if utils.norm(
                            coordinates.Coords(tile[0], tile[1]) - knowledge.position
                        )
                        <= self.curr_params.mist_escape_limit
                        and utils.misted(tile_description)
                    ]
                )
            ):
                runaway_cords: coordinates.Coords = self.mist_escape_target(knowledge)
                if runaway_cords is not None:
                    self.curr_targets_set.add(Goal("mist", 0 - self.t, runaway_cords))

            # potion and fire
            for key, tile in knowledge.visible_tiles.items():
                fire_free = True
                for effect in tile.effects:
                    if effect.type == "fire":
                        if knowledge.position == key:
                            self.in_fire = True
                        fire_free = False
                if (
                    fire_free
                    and tile.consumable
                    and not self.curr_params.ignore_potion
                    and not utils.misted(tile)
                ):
                    self.curr_targets_set.add(
                        Goal(
                            "potion",
                            500,
                            coordinates.Coords(key[0], key[1]),
                            True,
                            None,
                        )
                    )

            # swap weapon to better; always swap scroll with 0 charges and try to swap anything not in 'better_weapons' to anything in 'better_weapons'
            if not self.curr_params.ignore_weapon:
                weapons_list = [
                    (
                        cords[0],
                        cords[1],
                        self.path_finder.shortest_path(
                            knowledge.position.x,
                            knowledge.position.y,
                            cords[0],
                            cords[1],
                        )[0],
                        tile.loot,
                    )
                    for cords, tile in knowledge.visible_tiles.items()
                    if tile.loot and tile.loot.name in self.curr_params.better_weapons
                ]

                if len(weapons_list) > 0:
                    weapons_list = sorted(weapons_list, key=lambda x: x[2])
                    if self.weapon.name == "scroll" and self.charges == 0:
                        self.curr_targets_set.add(
                            Goal(
                                "weapon",
                                -2000,
                                coordinates.Coords(
                                    weapons_list[0][0], weapons_list[0][1]
                                ),
                                True,
                                None,
                            )
                        )

                    curr_index: int = (
                        self.curr_params.better_weapons.index(self.weapon.name)
                        if self.weapon.name in self.curr_params.better_weapons
                        else 100
                    )
                    weapons_list = sorted(weapons_list, key=lambda x: x[2])
                    weapons_list = [
                        x
                        for x in weapons_list
                        if x[3].name in self.curr_params.better_weapons
                        and self.curr_params.better_weapons.index(x[3].name)
                        < curr_index
                    ]
                    if len(weapons_list) > 0:
                        self.curr_targets_set.add(
                            Goal(
                                "weapon",
                                200,
                                coordinates.Coords(
                                    weapons_list[0][0], weapons_list[0][1]
                                ),
                                True,
                                None,
                            )
                        )

            # remove reached target
            to_remove = []
            for target in self.curr_targets_set:
                if (
                    target.vanishable
                    and target.journey_target.x == knowledge.position.x
                    and target.journey_target.y == knowledge.position.y
                    and (target.facing is None or target.facing == self.facing)
                ):
                    to_remove.append(target)

            for target in to_remove:
                self.curr_targets_set.remove(target)

            # if no goal and explore randomize goal
            if self.curr_params.explore and len(self.curr_targets_set) == 0:
                self.curr_targets_set.add(
                    Goal("hide", 1000, random.choice(self.HIDING_SPOTS), True)
                )

            # print('-' * 40)
            # print(self.first_name, knowledge.position, len(knowledge.visible_tiles), self.menhir, self.mist, self.weapon.name, len(self.curr_targets_set), self.facing, self.prev_weapon)

            # attack
            attack_coords: list[coordinates.Coords] = get_attack_positions(
                knowledge.position, self.weapon.name, self.facing
            )
            possible_targets: list[coordinates.Coords] = [
                coordinates.Coords(coords[0], coords[1])
                for (coords, description) in knowledge.visible_tiles.items()
                if utils.passable(description)
                and (description.type != "forest")
                and description.character
                and coords != knowledge.position
            ]
            if not self.curr_params.ignore_possible_attack_opportunity and bool(
                set(attack_coords) & set(possible_targets)
            ):
                to_remove = []
                for target in self.curr_targets_set:
                    if target.name == "attack_position":
                        to_remove.append(target)

                for target in to_remove:
                    self.curr_targets_set.remove(target)

                if self.weapon.name == "scroll":
                    self.charges -= 1
                return characters.Action.ATTACK

            if (
                not self.curr_params.ignore_possible_attack_opportunity
                and len(possible_targets) > 0
            ):
                # print("targets:", possible_targets)
                targets_distance: list[int, coordinates.Coords] = [
                    (utils.norm(coords - knowledge.position), coords)
                    for coords in possible_targets
                ]
                min_dist_to_champion, closest_chamption_coords = min(
                    targets_distance, key=lambda x: x[0]
                )
                # print("MIN DIST", min_dist_to_champion, closest_chamption_coords)

                if (
                    min_dist_to_champion is not None
                    and min_dist_to_champion < self.agress_turn_on_dst
                ):
                    # closest_champion :characters.ChampionDescription = knowledge.visible_tiles[closest_chamption_coords].character
                    self.add_killer_goals(knowledge, closest_chamption_coords, 100)

            curr_target: Goal = None
            if len(self.curr_targets_set) > 0:
                curr_target = min(self.curr_targets_set)
                # print("curr target:", curr_target.name, curr_target.journey_target, curr_target.facing)

                path = self.path_finder.shortest_path(
                    knowledge.position.x,
                    knowledge.position.y,
                    curr_target.journey_target.x,
                    curr_target.journey_target.y,
                )
                facing_action = self.determine_target_facing(
                    knowledge.position, curr_target
                )
                if facing_action is not None:
                    return facing_action

                if path is not None:
                    dst, target = path

                    if dst <= curr_target.wandering:
                        if curr_target.facing is not None:
                            facing_action = self.determine_target_facing(
                                knowledge.position, curr_target, [curr_target.facing]
                            )
                            if facing_action is not None:
                                return facing_action
                    target_facing = utils.str_to_facing(target)
                    next_position_on_the_journey = (
                        knowledge.position + utils.facing_to_cords(target_facing)
                    )

                    next_position_on_the_journey_tile_description: tiles.TileDescription = knowledge.visible_tiles.get(
                        next_position_on_the_journey
                    )
                    # print("NEXT: ", knowledge.position, target_facing, next_position_on_the_journey, next_position_on_the_journey_tile_description)
                    if (
                        next_position_on_the_journey_tile_description is not None
                        and next_position_on_the_journey_tile_description.character
                    ):
                        facing_action = self.determine_target_facing(
                            knowledge.position, curr_target, [target_facing]
                        )
                        # print("facing", facing_action)
                        if self.curr_params.attack_when_in_path:
                            self.add_killer_goals(
                                knowledge, next_position_on_the_journey, -5
                            )
                        else:
                            self.curr_targets_set.remove(curr_target)
                        if self.weapon.name != "amulet" and facing_action is not None:
                            return facing_action

                    else:
                        dst, target = path
                        if dst != 0:
                            move = None
                            if target == "UP":
                                move = utils.move_up(self.facing)
                            elif target == "DOWN":
                                move = utils.move_down(self.facing)
                            elif target == "LEFT":
                                move = utils.move_left(self.facing)
                            elif target == "RIGHT":
                                move = utils.move_right(self.facing)
                            if move is not None:
                                return move
        except Exception:
            pass

        if self.weapon.name == "scroll":  # dont randomly use weapon when scroll
            return random.choice(POSSIBLE_ACTIONS[:-1])
        return random.choice(POSSIBLE_ACTIONS)

    def add_killer_goals(
        self,
        knowledge: characters.ChampionKnowledge,
        cords_to_kill: coordinates.Coords,
        priority: int = 100,
    ) -> None:
        for attack_facing in [
            characters.Facing.UP,
            characters.Facing.DOWN,
            characters.Facing.LEFT,
            characters.Facing.RIGHT,
        ]:
            closest_champion_attackable_coords: set[coordinates.Coords] = set(
                get_attack_positions(cords_to_kill, self.weapon.name, attack_facing)
            )
            # ^ is a set of Cords that cords_to_kill can be attacked from
            if len(closest_champion_attackable_coords) == 0:
                return
            closest_champion_attackable_coords_free = []

            for coords in closest_champion_attackable_coords:
                path = self.path_finder.shortest_path(
                    knowledge.position.x, knowledge.position.y, coords.x, coords.y
                )
                if path is not None:
                    dst, _ = path
                    closest_champion_attackable_coords_free.append((dst, coords))

            if len(closest_champion_attackable_coords_free) > 0:
                min_dst, target = min(
                    closest_champion_attackable_coords_free, key=lambda x: x[0]
                )
                # print("TARGETED", min_dst, target,attack_facing.opposite(), closest_champion_attackable_coords, closest_champion_attackable_coords_free)
                self.curr_targets_set.add(
                    Goal(
                        "attack_position",
                        priority + min_dst,
                        target,
                        True,
                        attack_facing.opposite(),
                    )
                )

    def mist_escape_target(
        self, knowledge: characters.ChampionKnowledge
    ) -> coordinates.Coords:
        mist_escape_targets: list[coordinates.Coords] = []

        for tile, tile_description in knowledge.visible_tiles.items():
            if utils.passable(tile_description) and not utils.misted(tile_description):
                path = self.path_finder.shortest_path(
                    knowledge.position.x, knowledge.position.y, tile[0], tile[1]
                )
                if path is not None:
                    mist_escape_targets.append(coordinates.Coords(tile[0], tile[1]))

        best_distance = -1
        best_target = None

        for target in mist_escape_targets:
            min_distance = float("inf")

            for misted_coord in self.misted_set:
                path = self.path_finder.shortest_path(
                    target.x, target.y, misted_coord.x, misted_coord.y
                )
                if path is not None:
                    distance, _ = path
                    min_distance = min(min_distance, distance)

            if min_distance > best_distance:
                best_distance = min_distance
                best_target = target

        return best_target

    def determine_target_facing(
        self,
        curr_position: coordinates.Coords,
        curr_target: Goal,
        target_facing: list[characters.Facing] = [],
    ):
        if target_facing == []:
            self.target_facings = []
            if curr_target.journey_target.y - curr_position.y >= 0:
                self.target_facings.append(characters.Facing.DOWN)
            if curr_target.journey_target.y - curr_position.y <= 0:
                self.target_facings.append(characters.Facing.UP)
            if curr_target.journey_target.x - curr_position.x >= 0:
                self.target_facings.append(characters.Facing.RIGHT)
            if curr_target.journey_target.x - curr_position.x <= 0:
                self.target_facings.append(characters.Facing.LEFT)
        else:
            self.target_facings = target_facing
        if self.facing in self.target_facings:
            return None

        if self.facing == characters.Facing.UP:
            if characters.Facing.LEFT in self.target_facings:
                return characters.Action.TURN_LEFT
            elif characters.Facing.RIGHT in self.target_facings:
                return characters.Action.TURN_RIGHT

        if self.facing == characters.Facing.DOWN:
            if characters.Facing.LEFT in self.target_facings:
                return characters.Action.TURN_RIGHT
            elif characters.Facing.RIGHT in self.target_facings:
                return characters.Action.TURN_LEFT

        if self.facing == characters.Facing.LEFT:
            if characters.Facing.UP in self.target_facings:
                return characters.Action.TURN_RIGHT
            if characters.Facing.DOWN in self.target_facings:
                return characters.Action.TURN_LEFT

        if self.facing == characters.Facing.RIGHT:
            if characters.Facing.UP in self.target_facings:
                return characters.Action.TURN_LEFT
            if characters.Facing.DOWN in self.target_facings:
                return characters.Action.TURN_RIGHT
        return None

    def praise(self, score: int) -> None:
        if self.thompson:
            self.thompson.update(self.curr_thompson_name, score)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        if self.thompson:
            self.curr_thompson_name, self.curr_params = self.thompson.select_arm()
            # print(" ", self.curr_thompson_name, " <- ")
            # print(self.thompson)
        self.menhir = None
        self.mist = None
        self.facing = None
        self.weapon = None
        self.curr_targets_set = set()
        self.charges = 5
        self.in_fire = False
        self.target_facings = []
        self.spawned = False
        self.t = 0
        self.prev_weapon = None
        self.previous_position = None
        self.misted_set = set()

    def register(self, key) -> None:
        pass

    @property
    def name(self) -> str:
        return f"Rustler{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RUSTLER


POTENTIAL_CONTROLLERS = [
    Rustler(),
]
