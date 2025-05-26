import random
from typing_extensions import override
from typing import Tuple, Dict, List, Set

import numpy as np

from gupb import controller
from gupb.controller.rustler import utils
from gupb.controller.rustler.goal import Goal
from gupb.controller.rustler.dynamic_grid_pathfinder import DynamicGridPathfinder
from gupb.controller.rustler.settings import Settings
from gupb.controller.rustler.weapon_util import get_attack_positions
from gupb.model import arenas, characters, coordinates, tiles, weapons

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

from gupb.scripts.arena_generator import MAX_SIZE
ARENA_SIZE_X = max(MAX_SIZE, 30)
ARENA_SIZE_Y = max(MAX_SIZE, 30)


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

    def __init__(self, arms: Dict[str, Settings], no_players: int, min_evals: Dict[str, int]):
        self.arms = arms
        self.successes = {arm: 1 for arm in arms}
        self.failures = {arm: 1 for arm in arms}
        self.max_reward = self.REWARDS[no_players]
        self.evals = {arm: 0 for arm in arms}
        self.min_evals = min_evals

    def select_arm(self) -> Tuple[str, Settings]:
        # Forced exploration
        forced = [arm for arm in self.arms if arm in self.min_evals and self.evals[arm] < self.min_evals.get(arm, 0)]
        if forced:
            chosen = random.choice(forced)
            return chosen, self.arms[chosen]
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
            self.evals[chosen_name] += 1

    def __str__(self):
        str = ''
        for key in self.arms.keys():
            str += f'{key}: + {self.successes[key]:.2f} - {self.failures[key]:.2f} / {self.evals[key]:.2f} \n'
        return str


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Rustler(controller.Controller):
    """
    Oxidized, Blazingly Fast, Overengineered for Survival.
    """

    def __init__(self, first_name: str = 'Rustler', **kwargs):
        self.first_name: str = first_name
        self.hiding_spots: Set[coordinates.Coords] = set()
        self.path_finder: DynamicGridPathfinder = DynamicGridPathfinder(ARENA_SIZE_X, ARENA_SIZE_Y)

        self.menhir: coordinates.Coords | None = None
        self.mist: coordinates.Coords | None = None
        self.facing: characters.Facing | None = None
        self.weapon: weapons.WeaponDescription | None = None
        self.prev_weapon: weapons.WeaponDescription | None = None
        self.previous_position: coordinates.Coords | None = None
        self.curr_targets_set: Set[Goal] = set()
        self.charges: int = 5
        self.target_facings: List[str] = []
        self.spawned: bool = False
        self.thompson: ThompsonSampling | None = None
        self.curr_thompson_name: str = ''
        self.curr_params: Settings | None = None
        self.t: int = 0
        self.misted_set: Set[coordinates.Coords] = set()

        self.tile_knowledge: Dict[
            coordinates.Coords, Tuple[tiles.TileDescription, int]
        ] = {}

        if not kwargs:
            pass
            # Thompson Sampling algo will be run later bc we need to know no_players
        else:
            self.curr_params = Settings(**kwargs)

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Rustler):
            return False

        return self.first_name == other.first_name

    @override
    def __hash__(self) -> int:
        return hash(self.first_name)

    def init_thompson_sampling(self, no_players: int) -> None:
        arms = {
            "KILER_HUNTER": {
                "aggression_turn_dst": 100,
                "explore": True,
                "disable_hidden_spots": True,
                "menhir_turns_off_exploration": False,
            },
            "KILER_HUNTER_SLOW": {
                "aggression_turn_dst": 100,
                "explore": True,
                "disable_hidden_spots": True,
                "menhir_turns_off_exploration": False,
                "priority_potion": 30,
                "priority_weapon_better": 40
            },
            'KILER': {
                'aggression_turn_dst': 100,
                'explore': False,
            },
            'NO_HIDE': {
                'disable_hidden_spots': True,
                'aggression_turn_dst': 100,
            },
            'ARCHER_AGRESS': {
                'better_weapons': [
                    'bow_loaded',
                    'bow_unloaded',
                    'amulet',
                    'axe',
                    'sword',
                ],
                'auto_load_bow': True,
                'bow_disables_aggro': False,
                'aggression_turn_dst': 100,
            },
            'ARCHER_AGRESS_EXPLORE': {
                'better_weapons': [
                    'bow_loaded',
                    'bow_unloaded',
                    'amulet',
                    'axe',
                    'sword',
                ],
                'auto_load_bow': True,
                'bow_disables_aggro': False,
                'aggression_turn_dst': 100,
                'explore': True,
                'vanishing_forest': True
            },
            'ARCHER': {
                'better_weapons': [
                    'bow_loaded',
                    'bow_unloaded',
                    'amulet',
                    'axe',
                    'sword',
                ],
                'auto_load_bow': True,
                'bow_disables_aggro': False,
            },
            'PASSIVE': {
                'aggression_turn_dst': 0,
                'menhir_ignore': True,
            },
            'CAMPER': {
                'ignore_weapon': True,
                'aggression_turn_dst': 1,
            },
            'CAMPER_NO_MENHIR': {
                'ignore_weapon': True,
                'aggression_turn_dst': 1,
                'menhir_ignore': True,
            },
            'NORMAL': {'aggression_turn_dst': 1},
            'NORMAL_NO_MENHIR': {
                'aggression_turn_dst': 1,
                'menhir_ignore': True,
            },
            'SWORD': {
                'better_weapons': [
                    'sword',
                    'axe',
                    'amulet',
                    'bow_loaded',
                    'bow_unloaded',
                    'scroll',
                ],
                "aggression_turn_dst": 100,
                "explore": True,
                "menhir_ignore": False,
                "disable_hidden_spots": True,
                "menhir_turns_off_exploration": False,
            },
            'AXE': {
                'better_weapons': [
                    'axe',
                    'sword',
                    'amulet',
                    'bow_loaded',
                    'bow_unloaded',
                    'scroll',
                ],
                'aggression_turn_dst': 100,
                'explore': True,
                'menhir_ignore': False,
            },
        }
        min_evals = { 
            'KILER_HUNTER': 3,
            'KILER': 3,
            'KILER_HUNTER_SLOW': 3,
            'AXE': 3,
            'ARCHER_AGRESS': 3,
            'ARCHER': 3,
            'SWORD': 3,
            'NORMAL': 3
        }

        arms = {key: Settings(**value) for (key, value) in arms.items()}
        self.thompson = ThompsonSampling(arms, no_players, min_evals)
        self.curr_thompson_name, self.curr_params = self.thompson.select_arm()

    def go_to_hidden_spot(self, knowledge: characters.ChampionKnowledge):
        to_remove = {
            target for target in self.curr_targets_set if target.name == "hide"
        }
        self.curr_targets_set.difference_update(to_remove)
        valid_spots = [
            (utils.norm(spot - knowledge.position), spot)
            for spot in self.hiding_spots
            if (
                self.tile_knowledge.get(spot)
                and (
                    spot == knowledge.position
                    or self.tile_knowledge[spot][0].character is None
                )
            )
        ]
        if not valid_spots:
            return
        dst, cords = min(valid_spots, key=lambda x: x[0])
        self.curr_targets_set.add(
            Goal('hide', self.curr_params.priority_hide, cords, self.curr_params.vanishing_forest, None, 0)
        )

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.t += 1
            if self.curr_params is None:
                self.init_thompson_sampling(knowledge.no_of_champions_alive)
            if self.curr_params.true_random:
                return random.choice(POSSIBLE_ACTIONS)

            curr_tile = knowledge.visible_tiles[knowledge.position]
            self.update_tile_knowledge(knowledge)
            self.facing = curr_tile.character.facing
            # hiding spots
            for tile_cords, knowledge_tile in knowledge.visible_tiles.items():
                if knowledge_tile.type == 'forest':
                    self.hiding_spots.add(
                        coordinates.Coords(tile_cords[0], tile_cords[1])
                    )

            if not self.curr_params.disable_hidden_spots:
                if self.hiding_spots:
                    self.go_to_hidden_spot(knowledge)
            # weapons
            if (
                not self.curr_params.ignore_weapon
                and self.prev_weapon is not None
                and self.prev_weapon.name != 'knife'
                and self.prev_weapon.name != self.weapon.name
                and self.prev_weapon.name in self.curr_params.better_weapons
                and (
                    self.weapon.name not in self.curr_params.better_weapons
                    or self.curr_params.better_weapons.index(self.prev_weapon.name)
                    < self.curr_params.better_weapons.index(self.weapon.name)
                )
            ):
                self.curr_targets_set.add(
                    Goal('weapon', self.curr_params.priority_weapon_go_back, self.previous_position, True, None, 0)
                )
                # ^ above if adds weapon goal when we accidently swapped good weapon for a bad one and moved on
                # (remembers dropping it even if its not in knowledge.visible_tiles)
            if self.previous_position != knowledge.position:
                self.prev_weapon = self.weapon
            self.previous_position = knowledge.position
            self.weapon = knowledge.visible_tiles[knowledge.position].character.weapon

            # scroll and bow
            if self.weapon.name != 'scroll':
                self.charges = 5
            if self.weapon.name == 'scroll' and self.charges == 0:
                self.agress_turn_on_dst = 0
            if self.curr_params.bow_disables_aggro and self.weapon.name[0:3] == 'bow':
                self.agress_turn_on_dst = 0
            else:
                self.agress_turn_on_dst = self.curr_params.aggression_turn_dst
            if self.curr_params.auto_load_bow and self.weapon.name == 'bow_unloaded':
                return characters.Action.ATTACK
            # menhir
            if self.menhir is None and not self.curr_params.menhir_ignore:
                for key, tile in knowledge.visible_tiles.items():
                    if tile.type == 'menhir':
                        self.menhir = coordinates.Coords(key[0], key[1])
                        if self.mist is not None:
                            self.curr_targets_set.add(
                                Goal("menhir", self.curr_params.priority_menhir, self.menhir, False, None, wandering=3)
                            )

            # mist
            if not self.curr_params.mist_ignore:
                for key, tile in knowledge.visible_tiles.items():
                    for effect in tile.effects:
                        if effect.type == 'mist':
                            if coordinates.Coords(key[0], key[1]) not in self.misted_set:
                                self.misted_set.add(coordinates.Coords(key[0], key[1]))

                            self.mist = True
                            if self.menhir and not self.curr_params.menhir_ignore:
                                self.curr_targets_set.add(
                                    Goal(
                                        "menhir", self.curr_params.priority_menhir, self.menhir, False, None, wandering=self.curr_params.menhir_wandering
                                    )
                                )

            if (
                not self.curr_params.mist_ignore
                and self.mist
                and not (self.menhir and utils.norm(knowledge.position - self.menhir) <= self.curr_params.menhir_wandering)
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
                runaway_cords_tuple = self.path_finder.get_candidate(knowledge.position.x, knowledge.position.y)

                if runaway_cords_tuple is not None:
                    runaway_cords = coordinates.Coords(runaway_cords_tuple[0], runaway_cords_tuple[1])
                    if self.menhir is not None and not self.curr_params.menhir_ignore:
                        self.curr_targets_set.add(Goal('mist', self.curr_params.priority_mist_with_menhir, runaway_cords, True, None, 0))
                    else:
                        self.curr_targets_set.add(
                            Goal("mist", self.curr_params.priority_mist_no_menhir - self.curr_params.priority_mist_no_menhir_time_multiplier * self.t, runaway_cords, True, None, 0)
                        )

            # potion and fire
            for key, tile in knowledge.visible_tiles.items():
                fire_free = True
                for effect in tile.effects:
                    if effect.type == 'fire':
                        fire_free = False
                if (
                    fire_free
                    and tile.consumable
                    and not self.curr_params.ignore_potion
                    and not utils.misted(tile)
                ):
                    dst = utils.norm(coordinates.Coords(key[0], key[1]) - knowledge.position)
                    self.curr_targets_set.add(
                        Goal(
                            "potion",
                            self.curr_params.priority_potion - self.curr_params.priority_potion_time_multiplier * self.t + self.curr_params.priority_potion_dst_multiplier * dst,
                            coordinates.Coords(key[0], key[1]),
                            True,
                            None,
                            0
                        )
                    )

            # swap weapon to better; always swap scroll with 0 charges and try to swap anything not in 'better_weapons' to anything in 'better_weapons'
            if not self.curr_params.ignore_weapon:
                weapons_list = [
                    (
                        cords[0],
                        cords[1],
                        shortest_path[0],  # Using the stored shortest path result
                        tile.loot,
                    )
                    for cords, tile in knowledge.visible_tiles.items()
                    if tile.loot
                    and tile.loot.name in self.curr_params.better_weapons
                    and (
                        shortest_path := self.path_finder.shortest_path(
                            knowledge.position.x,
                            knowledge.position.y,
                            cords[0],
                            cords[1],
                        )
                    )  # Assigning shortest_path once
                ]

                if len(weapons_list) > 0:
                    weapons_list = sorted(weapons_list, key=lambda x: x[2])
                    if self.weapon.name == 'scroll' and self.charges == 0:
                        self.curr_targets_set.add(
                            Goal(
                                'weapon',
                                self.curr_params.priority_weapon_no_scroll,
                                coordinates.Coords(
                                    weapons_list[0][0], weapons_list[0][1]
                                ),
                                True,
                                None,
                                0
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
                        and self.curr_params.better_weapons.index(x[3].name) < curr_index
                    ]
                    if len(weapons_list) > 0:
                        self.curr_targets_set.add(
                            Goal(
                                'weapon',
                                self.curr_params.priority_weapon_better,
                                coordinates.Coords(
                                    weapons_list[0][0], weapons_list[0][1]
                                ),
                                True,
                                None,
                                0
                            )
                        )

            # remove reached target
            to_remove = {
                    target
                    for target in self.curr_targets_set if
                    target.vanishable
                    and abs(target.journey_target.x - knowledge.position.x) <= target.wandering
                    and abs(target.journey_target.y - knowledge.position.y) <= target.wandering
                    and (target.facing is None or target.facing == self.facing)
                }
            self.curr_targets_set.difference_update(to_remove)
            # if no goal and explore set goal to closest unexplored tile
            if (
                self.curr_params.explore
                and len(self.curr_targets_set) == 0
                and not (self.menhir and self.curr_params.menhir_turns_off_exploration)
            ):
                reachable = self.path_finder.distances_from_start(
                    knowledge.position.x, knowledge.position.y, False, float('inf')
                )
                reachable = {
                    coordinates.Coords(x, y): dst
                    for (x, y), dst in reachable.items()
                    if coordinates.Coords(x, y) not in self.tile_knowledge
                }
                if len(reachable) > 0:
                    x, y = min(reachable, key=reachable.get)
                    self.curr_targets_set.add(
                        Goal(
                            'explore',
                            self.curr_params.priority_explore,
                            coordinates.Coords(x, y),
                            True,
                            None,
                            3
                        )
                    )
            # attack
            attack_coords: List[coordinates.Coords] = get_attack_positions(
                knowledge.position, self.weapon.name, self.facing, self.tile_knowledge
            )
            possible_targets: List[coordinates.Coords] = [
                coordinates.Coords(coords[0], coords[1])
                for (coords, description) in knowledge.visible_tiles.items()
                if utils.passable(description)
                and (description.type != 'forest')
                and description.character
                and coords != knowledge.position
            ]
            if not self.curr_params.ignore_possible_attack_opportunity and bool(
                set(attack_coords) & set(possible_targets)
            ):
                to_remove = {
                    target
                    for target in self.curr_targets_set
                    if target.name == 'attack_position'
                }
                self.curr_targets_set.difference_update(to_remove)

                if self.weapon.name == 'scroll':
                    self.charges -= 1
                return characters.Action.ATTACK

            if (
                not self.curr_params.ignore_possible_attack_opportunity
                and len(possible_targets) > 0
            ):
                targets_distance: List[int, coordinates.Coords] = [
                    (utils.norm(coords - knowledge.position), coords)
                    for coords in possible_targets
                ]
                min_dist_to_champion, closest_chamption_coords = min(
                    targets_distance, key=lambda x: x[0]
                )

                if (
                    min_dist_to_champion is not None
                    and min_dist_to_champion < self.agress_turn_on_dst
                ):
                    # closest_champion :characters.ChampionDescription = knowledge.visible_tiles[closest_chamption_coords].character
                    self.add_killer_goals(
                        knowledge, closest_chamption_coords, self.curr_params.priority_killer_goals_normal - self.curr_params.priority_killer_goals_normal_time_multiplier * self.t
                    )

            curr_target: Goal | None = min(self.curr_targets_set, default=None)
            target_index: int = 0
            iterations: int = 0
            max_iterations: int = 10

            while curr_target:
                iterations += 1
                if iterations > max_iterations:
                    break
                # print("curr target:", curr_target.name, curr_target.priority, curr_target.journey_target, curr_target.facing)
                if (
                    curr_target.name == 'explore'
                    and self.tile_knowledge.get(curr_target.journey_target) is not None
                ):
                    self.curr_targets_set.remove(curr_target)
                    curr_target = min(self.curr_targets_set, default=None)
                    continue

                if curr_target.name == 'menhir' and self.weapon.name != 'scroll':
                    tile_description, _ = self.tile_knowledge.get(
                        curr_target.journey_target, (None, None)
                    )
                    if (
                        tile_description.character is not None
                        and curr_target.journey_target != knowledge.position
                    ):
                        self.add_killer_goals(
                            knowledge, curr_target.journey_target, self.curr_params.priority_killer_goals_menhir - self.curr_params.priority_killer_goals_menhir_time_multiplier * self.t
                        )
                        curr_target = min(self.curr_targets_set, default=None)
                        continue

                if (
                    curr_target.name == "attack_position"
                    and self.weapon.name == "scroll"
                    and self.charges == 0
                ):
                    target_index += 1
                    curr_target = utils.quickselect(self.curr_targets_set, target_index)
                    continue

                path = self.path_finder.shortest_path(
                    knowledge.position.x,
                    knowledge.position.y,
                    curr_target.journey_target.x,
                    curr_target.journey_target.y,
                )

                # print("PATH", path)

                if path is not None:
                    dst, target = path
                    # target: Facing = facing to go on path
                    # self.facing: Facing = character facing
                    # curr_target.facing: Facing = target facing
                    if target == 'STAY':
                        facing_action = self.determine_target_facing(
                            knowledge.position, curr_target, [curr_target.facing]
                        )
                        if (
                            facing_action is not None
                            and self.facing != curr_target.facing
                        ):
                            return facing_action

                    if dst <= curr_target.wandering:
                        target_index += 1
                        if curr_target.name == 'menhir':
                            self.delete_out_of_reach_goals(self.curr_params.menhir_wandering + 1)
                        curr_target = utils.quickselect(
                            self.curr_targets_set, target_index
                        )  # Returns the nth minimal element
                        continue

                    path_facing = utils.str_to_facing(target)
                    next_position_on_the_journey = (
                        knowledge.position + utils.facing_to_cords(path_facing)
                    )
                    facing_action = self.determine_target_facing(
                        knowledge.position, curr_target, [path_facing]
                    )
                    next_position_on_the_journey_tile_description: tiles.TileDescription = knowledge.visible_tiles.get(
                        next_position_on_the_journey
                    )
                    # print("NEXT: ", knowledge.position, path_facing, next_position_on_the_journey, next_position_on_the_journey_tile_description)
                    if (
                        next_position_on_the_journey_tile_description is not None
                        and next_position_on_the_journey_tile_description.character
                    ):
                        if (
                            self.curr_params.attack_when_in_path
                            and next_position_on_the_journey_tile_description.type
                            != 'forest'
                        ):
                            self.add_killer_goals(
                                knowledge,
                                next_position_on_the_journey,
                                self.curr_params.priority_killer_goals_path - self.curr_params.priority_killer_goals_path_time_multiplier * self.t,
                            )
                            if (
                                self.weapon.name != 'amulet'
                                and facing_action is not None
                                and self.facing != curr_target.facing
                            ):
                                return facing_action

                            curr_target = min(self.curr_targets_set, default=None)
                            continue

                        else:
                            if curr_target in self.curr_targets_set:
                                self.curr_targets_set.remove(curr_target)
                                # next coords on path is an occupied forest
                                # TODO: add goal to run away ??? 
                            else:
                                pass  # TODO ???

                    else:
                        dst, target = path
                        if (
                            dst != 0
                            and utils.str_to_facing(target).opposite() != self.facing
                        ):
                            move = None
                            if target == 'UP':
                                move = utils.move_up(self.facing)
                            elif target == 'DOWN':
                                move = utils.move_down(self.facing)
                            elif target == 'LEFT':
                                move = utils.move_left(self.facing)
                            elif target == 'RIGHT':
                                move = utils.move_right(self.facing)
                            if move is not None:
                                return move

                    facing_action = self.determine_target_facing(
                        knowledge.position, curr_target, [path_facing]
                    )
                    if facing_action is not None and self.facing != curr_target.facing:
                        return facing_action

                else:
                    target_index += 1
                    curr_target = utils.quickselect(
                        self.curr_targets_set, target_index
                    )  # Returns the nth minimal element
                    continue

                break
            return random.choice(
                [characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
            )
        except Exception as e:
            pass

        if self.weapon.name == 'scroll':  # dont randomly use weapon when scroll
            return random.choice(POSSIBLE_ACTIONS[:-1])
        return random.choice(POSSIBLE_ACTIONS)

    def delete_out_of_reach_goals(self, threshold):
        if not self.menhir:
            return
        
        distances_dict = self.path_finder.distances_from_start(
            self.menhir[0], self.menhir[1], False, threshold + 1
        )
        to_remove = {
            target for target in self.curr_targets_set 
            if distances_dict.get((target.journey_target.x, target.journey_target.y), 1000) > threshold
        }
        self.curr_targets_set.difference_update(to_remove)

    def update_tile_knowledge(self, knowledge: characters.ChampionKnowledge) -> None:
        for tile_coords in self.misted_set:
            self.path_finder.update_cell(tile_coords[0], tile_coords[1], 8)
        for tile_coords, tile_desc in knowledge.visible_tiles.items():
            self.tile_knowledge[coordinates.Coords(tile_coords[0], tile_coords[1])] = (
                tile_desc,
                self.t,
            )
            if not utils.passable(tile_desc):
                self.path_finder.update_cell(
                    tile_coords[0], tile_coords[1], self.path_finder.INF
                )
            elif coordinates.Coords(tile_coords[0], tile_coords[1]) in self.misted_set: #utils.misted(tile_desc):
                self.path_finder.update_cell(tile_coords[0], tile_coords[1], 8)
            elif utils.on_fire(tile_desc):
                self.path_finder.update_cell(tile_coords[0], tile_coords[1], 9)
            elif tile_desc.character is not None and tile_coords != knowledge.position:
                self.path_finder.update_cell(
                                tile_coords[0], 
                                tile_coords[1],
                                (5 if tile_desc.type == 'forest' else 2),
                            )
                facings = (
                    [tile_desc.character.facing]
                    if tile_desc.type != 'forest'
                    else [
                        characters.Facing.UP,
                        characters.Facing.DOWN,
                        characters.Facing.LEFT,
                        characters.Facing.RIGHT,
                    ]
                )
                for attack_facing in facings:
                    dangerous_cords = get_attack_positions(
                        coordinates.Coords(tile_coords[0], tile_coords[1]),
                        tile_desc.character.weapon.name,
                        attack_facing,
                        self.tile_knowledge,
                    )
                    for coords in dangerous_cords:
                        if (
                            coords[0] >= 0
                            and coords[0] < ARENA_SIZE_X
                            and coords[1] >= 0
                            and coords[1] < ARENA_SIZE_Y
                            and (
                                self.tile_knowledge.get(coords, None) is None
                                or self.tile_knowledge[coords][0].type
                                not in ["forest", "wall", "sea"]
                            )
                        ):
                            self.path_finder.update_cell(
                                coords[0],
                                coords[1],
                                (3 if tile_desc.type == 'forest' else 2),
                            )
            else:
                self.path_finder.update_cell(tile_coords[0], tile_coords[1], 1)

    def add_killer_goals(
        self,
        knowledge: characters.ChampionKnowledge,
        cords_to_kill: coordinates.Coords,
        priority: float = 100,
    ) -> int:
        no_added_goals: int = 0
        closest_champion_attackable_coords: set[Tuple[int, int]] = set()
        for attack_facing in (
            [
                characters.Facing.UP,
                characters.Facing.DOWN,
                characters.Facing.LEFT,
                characters.Facing.RIGHT,
            ]
            if self.weapon.name != "amulet"
            else [characters.Facing.UP]
        ):
            closest_champion_attackable_coords = closest_champion_attackable_coords.union(
                get_attack_positions(
                    cords_to_kill, self.weapon.name, attack_facing, self.tile_knowledge
                )
            )
        # ^ is a set of Cords that cords_to_kill can be attacked from
        if not closest_champion_attackable_coords:
            return
        dst, closest_champion_attackable_coords_free = self.path_finder.shortest_paths(knowledge.position.x, knowledge.position.y,
                                        [(cords[0], cords[1]) for cords in closest_champion_attackable_coords])

          
        if closest_champion_attackable_coords_free:
            target = random.choice(closest_champion_attackable_coords_free)
            self.curr_targets_set.add(
                Goal(
                    "attack_position",
                    priority + self.curr_params.priority_attack_position_dst_multiplier * dst,
                    coordinates.Coords(target[0], target[1]),
                    True,
                    attack_facing.opposite()
                    if self.weapon.name != 'amulet'
                    else None,
                    0
                )
            )
            no_added_goals += 1

        return no_added_goals

    def determine_target_facing(
        self,
        curr_position: coordinates.Coords,
        curr_target: Goal,
        target_facing: List[characters.Facing] = [],
    ):
        if target_facing == []:
            self.target_facings = []
            if curr_target.journey_target.y - curr_position.y >= 0:
                self.target_facings.append(characters.Facing.UP)
            if curr_target.journey_target.y - curr_position.y <= 0:
                self.target_facings.append(characters.Facing.DOWN)
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
            if characters.Facing.RIGHT in self.target_facings:
                return characters.Action.TURN_RIGHT
            if characters.Facing.DOWN in self.target_facings:
                return random.choice(
                    [characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
                )

        if self.facing == characters.Facing.DOWN:
            if characters.Facing.LEFT in self.target_facings:
                return characters.Action.TURN_RIGHT
            if characters.Facing.RIGHT in self.target_facings:
                return characters.Action.TURN_LEFT
            if characters.Facing.UP in self.target_facings:
                return random.choice(
                    [characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
                )

        if self.facing == characters.Facing.LEFT:
            if characters.Facing.UP in self.target_facings:
                return characters.Action.TURN_RIGHT
            if characters.Facing.DOWN in self.target_facings:
                return characters.Action.TURN_LEFT
            if characters.Facing.RIGHT in self.target_facings:
                return random.choice(
                    [characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
                )

        if self.facing == characters.Facing.RIGHT:
            if characters.Facing.UP in self.target_facings:
                return characters.Action.TURN_LEFT
            if characters.Facing.DOWN in self.target_facings:
                return characters.Action.TURN_RIGHT
            if characters.Facing.LEFT in self.target_facings:
                return random.choice(
                    [characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
                )
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
        self.target_facings = []
        self.spawned = False
        self.t = 0
        self.prev_weapon = None
        self.previous_position = None
        self.misted_set = set()

        self.tile_knowledge = {}
        self.path_finder = DynamicGridPathfinder(ARENA_SIZE_X, ARENA_SIZE_Y)
        self.hiding_spots = set()

    def register(self, key) -> None:
        pass

    @property
    def name(self) -> str:
        return f'Rustler{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RUSTLER


POTENTIAL_CONTROLLERS = [
    Rustler(),
]
