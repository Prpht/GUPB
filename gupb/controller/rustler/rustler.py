from dataclasses import dataclass, field
import random
from typing_extensions import override

import numpy as np

from gupb import controller
from gupb.controller.rustler import utils
from gupb.controller.rustler.goal import Goal
from gupb.controller.rustler.lpafinder import LPAFinder
from gupb.controller.rustler.weapon_util import get_attack_positions
from gupb.model import arenas, characters, coordinates, tiles, weapons

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

ARENA_SIZE_X = 30
ARENA_SIZE_Y = 30

@dataclass(slots=True)
class Settings:
    better_weapons: list[str] = field(default_factory=lambda: ["amulet", "axe", "sword", "bow_loaded", "bow_unloaded", "scroll"])
    blacklisted_letters: list[str] = field(default_factory=lambda: ["B", "C"])
    aggression_turn_dst: int = 3
    mist_escape_limit: int = 15
    menhir_ignore: bool = False
    mist_ignore: bool = False
    ignore_possible_attack_opportunity: bool = False
    closest_hidden: bool = True
    disable_hidden_spots: bool = False
    ignore_weapon: bool = False
    true_random: bool = False
    ignore_potion: bool = False
    bow_disables_aggro: bool = True
    explore: bool = False
    attack_when_in_path: bool = True
    auto_load_bow: bool = False
    menhir_turns_off_exploration: bool = True
    vanishing_forest: bool = False

class Hyperparams:
    def __init__(self, **kwargs):
        # Default values
        self.better_weapons: list[str] = kwargs.get(
            'better_weapons',
            ['amulet', 'axe', 'sword', 'bow_loaded', 'bow_unloaded', 'scroll'],
        )
        self.blacklisted_letters: list[str] = kwargs.get(
            'blacklisted_letters', ['B', 'C']
        )
        self.aggression_turn_dst: int = kwargs.get('aggression_turn_dst', 3)
        self.mist_escape_limit: int = kwargs.get('mist_escape_limit', 15)

        # Boolean settings
        self.menhir_ignore: bool = kwargs.get('menhir_ignore', False)
        self.mist_ignore: bool = kwargs.get('mist_ignore', False)
        self.ignore_possible_attack_opportunity: bool = kwargs.get(
            'ignore_possible_attack_opportunity', False
        )
        self.closest_hidden: bool = kwargs.get('closest_hidden', True)
        self.disable_hidden_spots: bool = kwargs.get('disable_hidden_spots', False)
        self.ignore_weapon: bool = kwargs.get('ignore_weapon', False)
        self.true_random: bool = kwargs.get('true_random', False)
        self.ignore_potion: bool = kwargs.get('ignore_potion', False)
        self.bow_disables_aggro: bool = kwargs.get('bow_disables_aggro', True)
        self.explore: bool = kwargs.get(
            'explore', False
        )  # randomize hidden spot when reached
        self.attack_when_in_path: bool = kwargs.get('attack_when_in_path', True)
        self.auto_load_bow: bool = kwargs.get('auto_load_bow', False)
        self.menhir_turns_off_exploration: bool = kwargs.get(
            'menhir_turns_off_exploration', True
        )
        self.vanishing_forest: bool = kwargs.get('vanishing_forest', False)


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

    def __init__(self, arms: dict[str, Hyperparams], no_players: int):
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
        str = ''
        for key in self.arms.keys():
            str += f'{key}: {self.successes[key]} {self.failures[key]} \n'
        return str


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Rustler(controller.Controller):
    """
    Oxidized, Blazingly Fast, Overengineered for Survival.
    """

    def __init__(self, first_name: str = 'Rustler', **kwargs):
        self.first_name: str = first_name
        self.hiding_spots: set[coordinates.Coords] = set()
        self.path_finder: LPAFinder = LPAFinder(ARENA_SIZE_X, ARENA_SIZE_Y)

        self.menhir: coordinates.Coords | None = None
        self.mist: coordinates.Coords | None = None
        self.facing: characters.Facing | None = None
        self.weapon: weapons.WeaponDescription | None = None
        self.prev_weapon: weapons.WeaponDescription | None = None
        self.previous_position: coordinates.Coords | None = None
        self.curr_targets_set: set[Goal] = set()
        self.charges: int = 5
        self.target_facings: list[str] = []
        self.spawned: bool = False
        self.thompson: ThompsonSampling | None = None
        self.curr_thompson_name: str = ''
        self.curr_params: Hyperparams | None = None
        self.t: int = 0
        self.misted_set: set[coordinates.Coords] = set()

        self.tile_knowledge: dict[
            coordinates.Coords, tuple[tiles.TileDescription, int]
        ] = {}

        if not kwargs:
            pass
            # Thompson Sampling algo will be run later bc we need to know no_players
        else:
            self.curr_params = Hyperparams(**kwargs)

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
            'FIRE': {
                'better_weapons': ['scroll', 'sword', 'axe', 'amulet'],
                'aggression_turn_dst': 100,
                'explore': False,
            },
            "KILER_HUNTER": {
                "aggression_turn_dst": 100,
                "explore": True,
                "disable_hidden_spots": True,
                "menhir_turns_off_exploration": False,
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
        arms = {key: Hyperparams(**value) for (key, value) in arms.items()}
        self.thompson = ThompsonSampling(arms, no_players)
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
            Goal('hide', 900, cords, self.curr_params.vanishing_forest)
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
                    Goal('weapon', -1001, self.previous_position, True, None)
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
                                Goal("menhir", -1000, self.menhir, False, wandering=0)
                            )

            # mist
            if not self.curr_params.mist_ignore:
                for key, tile in knowledge.visible_tiles.items():
                    for effect in tile.effects:
                        if effect.type == 'mist':
                            self.misted_set.add(coordinates.Coords(key[0], key[1]))
                            self.mist = True
                            if self.menhir and not self.curr_params.menhir_ignore:
                                self.curr_targets_set.add(
                                    Goal(
                                        "menhir", -1000, self.menhir, False, wandering=0
                                    )
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
                    if self.menhir is not None and not self.curr_params.menhir_ignore:
                        self.curr_targets_set.add(Goal('mist', 500, runaway_cords))
                    else:
                        self.curr_targets_set.add(
                            Goal("mist", 0 - self.t, runaway_cords)
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
                    self.curr_targets_set.add(
                        Goal(
                            "potion",
                            190 - self.t / 100,
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
                        and self.curr_params.better_weapons.index(x[3].name) < curr_index
                    ]
                    if len(weapons_list) > 0:
                        self.curr_targets_set.add(
                            Goal(
                                'weapon',
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
            if (
                self.curr_params.explore
                and len(self.curr_targets_set) == 0
                and not (self.menhir and self.curr_params.menhir_turns_off_exploration)
            ):
                reachable = self.path_finder.distances_from_start(
                    knowledge.position.x, knowledge.position.y
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
                            1001,
                            coordinates.Coords(x, y),
                            True,
                            None,
                        )
                    )
            # attack
            attack_coords: list[coordinates.Coords] = get_attack_positions(
                knowledge.position, self.weapon.name, self.facing, self.tile_knowledge
            )
            possible_targets: list[coordinates.Coords] = [
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
                targets_distance: list[int, coordinates.Coords] = [
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
                        knowledge, closest_chamption_coords, 100 - self.t / 10
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
                            knowledge, curr_target.journey_target, -10000 - self.t
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
                                -100 - self.t / 10,
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
        except Exception:
            pass

        if self.weapon.name == 'scroll':  # dont randomly use weapon when scroll
            return random.choice(POSSIBLE_ACTIONS[:-1])
        return random.choice(POSSIBLE_ACTIONS)

    def update_tile_knowledge(self, knowledge: characters.ChampionKnowledge) -> None:
        for tile_coords, tile_desc in knowledge.visible_tiles.items():
            self.tile_knowledge[coordinates.Coords(tile_coords[0], tile_coords[1])] = (
                tile_desc,
                self.t,
            )
            if not utils.passable(tile_desc):
                self.path_finder.update_cell(
                    tile_coords[0], tile_coords[1], self.path_finder.INF
                )
            elif utils.misted(tile_desc) or utils.on_fire(tile_desc):
                self.path_finder.update_cell(tile_coords[0], tile_coords[1], 9)
            elif tile_desc.character is not None and tile_coords != knowledge.position:
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
            closest_champion_attackable_coords: Set[coordinates.Coords] = set(
                get_attack_positions(
                    cords_to_kill, self.weapon.name, attack_facing, self.tile_knowledge
                )
            )
            # ^ is a set of Cords that cords_to_kill can be attacked from
            if not closest_champion_attackable_coords:
                return
            closest_champion_attackable_coords_free: Tuple[int, coordinates.Coords] = (
                None
            )
            for coords in closest_champion_attackable_coords:
                if not (
                    coords[0] >= 0
                    and coords[0] < ARENA_SIZE_X
                    and coords[1] >= 0
                    and coords[1] < ARENA_SIZE_Y
                ) or (
                    self.tile_knowledge.get(coords) is not None
                    and self.tile_knowledge[coords][0].type == 'forest'
                ):
                    continue
                path = self.path_finder.shortest_path(
                    knowledge.position.x, knowledge.position.y, coords.x, coords.y
                )
                if path is not None:
                    dst, _ = path
                    if (
                        closest_champion_attackable_coords_free is None
                        or dst < closest_champion_attackable_coords_free[0]
                    ):
                        closest_champion_attackable_coords_free = (dst, coords)

            if closest_champion_attackable_coords_free is not None:
                dst, target = closest_champion_attackable_coords_free
                self.curr_targets_set.add(
                    Goal(
                        "attack_position",
                        priority + dst / 100,
                        target,
                        True,
                        attack_facing.opposite()
                        if self.weapon.name != 'amulet'
                        else None,
                    )
                )
                no_added_goals += 1

        return no_added_goals

    def mist_escape_target(
        self, knowledge: characters.ChampionKnowledge
    ) -> coordinates.Coords:
        mist_escape_targets: list[coordinates.Coords] = []
        mist_escape_targets = self.path_finder.distances_from_start(
            knowledge.position.x, knowledge.position.y
        )
        mist_escape_targets = [
            coordinates.Coords(x, y) for x, y in mist_escape_targets.keys()
        ]

        best_distance = -1
        best_target = None

        for target in mist_escape_targets:
            min_distance = float('inf')

            for misted_coord in self.misted_set:
                min_distance = min(min_distance, utils.norm(target - misted_coord))

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
        self.path_finder = LPAFinder(ARENA_SIZE_X, ARENA_SIZE_Y)
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
