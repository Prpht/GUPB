import os
from collections import defaultdict
from itertools import chain, product
from queue import Queue
from typing import Callable, Iterator

import numpy as np
import torch
from gupb.controller.kirby_neural_networks import ActorLoss, ActorNet, CriticNet
from gupb.model import arenas, characters
from gupb.model.arenas import Arena

from gupb.model.characters import Facing, ChampionDescription
from gupb.model.coordinates import Coords
from gupb.model.tiles import TileDescription
from gupb.model.weapons import (
    Knife,
    Sword,
    Axe,
    Amulet,
    Scroll,
    WeaponDescription,
    Bow,
    Weapon,
)

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
    characters.Action.STEP_RIGHT,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_BACKWARD,
    characters.Action.DO_NOTHING,
]


def _fibonacci() -> Iterator[int]:
    yield 1
    yield 2
    a = 3
    b = 4
    while True:
        yield int(a)
        a, b = b, (a / 2.2) + b


ROUNDS_NO = 3001
BETA = 0.01
EPSILON = 0.00
LAMBDA = 0.5
ACTOR_LR_ARRAY: np.ndarray[float] = 1e-6 * (
    np.cumprod(np.full(shape=(ROUNDS_NO,), fill_value=0.993)) + 1e-2
)
CRITIC_LR_ARRAY: np.ndarray[float] = 1e-5 * (
    np.cumprod(np.full(shape=(ROUNDS_NO,), fill_value=0.993)) + 1e-2
)
BOTS_NO = 12  # 12
MAP_PADDING = 2
POLICIES_NUM = 7
STATE_SIZE = 24
DIRECTIONS_NUM = 4
STEP_SIZE = 200
TD_STEPS = 5

DISCOUNT_FACTOR_ARRAY = np.linspace(0.99, 0.99, ROUNDS_NO)

steps = ROUNDS_NO // STEP_SIZE + 1

EPSILON_ARRAY = np.linspace(
    EPSILON, 0.00, ROUNDS_NO
)  # TODO schodkowa zmiana / (wykładniczy)?
EPSILON_ARRAY = np.array(
    [
        EPSILON_ARRAY[(min(ROUNDS_NO, i + 200) // STEP_SIZE) * STEP_SIZE]
        for i, _ in enumerate(EPSILON_ARRAY)
    ]
)
DISCOUNT_FACTOR = DISCOUNT_FACTOR_ARRAY[0]
MAX_SCORE = [i for i, _ in zip(_fibonacci(), range(BOTS_NO))][-1]

weapons_dict = {
    Knife().description(): (0, 0, 0),
    Sword().description(): (0, 0, 1),
    WeaponDescription(name="bow_loaded"): (0, 1, 0),
    WeaponDescription(name="bow_unloaded"): (0, 1, 1),
    Axe().description(): (1, 0, 0),
    Amulet().description(): (1, 0, 1),
    Scroll().description(): (1, 1, 0),
}

weapons_hierarchy: dict[WeaponDescription, int] = {
    Knife().description(): -80,
    Sword().description(): 1,
    WeaponDescription(name="bow_loaded"): 3,
    WeaponDescription(name="bow_unloaded"): 3,
    Axe().description(): 3,
    Amulet().description(): 5,
    Scroll().description(): 6,
}

weapons_names_dict: dict[WeaponDescription, Weapon] = {
    Knife().description(): Knife(),
    Sword().description(): Sword(),
    WeaponDescription(name="bow_loaded"): Bow(),
    WeaponDescription(name="bow_unloaded"): Bow(),
    Axe().description(): Axe(),
    Amulet().description(): Amulet(),
    Scroll().description(): Scroll(),
}
directions_values: dict[Facing, tuple[int, int]] = {
    Facing.UP: (0, 0),
    Facing.DOWN: (1, 0),
    Facing.LEFT: (0, 1),
    Facing.RIGHT: (1, 1),
}

directions_to_rotations = {
    Facing.UP: lambda x: x,
    Facing.DOWN: lambda x: torch.rot90(x, 2),
    Facing.LEFT: lambda x: torch.rot90(x, 3),
    Facing.RIGHT: lambda x: torch.rot90(x, 1),
}

dir_to_coords_change = {
    Facing.UP: lambda x, y: (-x, y),
    Facing.DOWN: lambda x, y: (x, -y),
    Facing.LEFT: lambda x, y: (-y, -x),
    Facing.RIGHT: lambda x, y: (y, x),
}
neighbourhood_coords_list = [
    (-2, 0),
    (-1, 0),
    (0, 0),
    (-1, -1),
    (-1, 1),
    (0, -2),
    (0, -1),
    (0, 0),
    (0, 1),
    (0, 2),
    (1, 0),
    (1, 1),
    (1, -1),
    (2, 0),
]

directions_to_indices = {Facing.UP: 0, Facing.LEFT: 1, Facing.DOWN: 2, Facing.RIGHT: 3}
indices_to_directions = {val: key for key, val in directions_to_indices.items()}

device = "cuda" if torch.cuda.is_available() else "cpu"


def weapon_power(weapon_name):
    return getattr(weapons_names_dict[weapon_name].cut_effect(), "damage", 5)


def neighbourhood_4(position: tuple[int, int]):
    return [
        (position[0] + i, position[1] + j)
        for i, j in [(0, -1), (-1, 0), (0, 1), (1, 0)]
    ]  # UP, LEFT, DOWN, RIGHT


def distance_x_y(x: tuple[float, float]):
    return abs(x[0]) + abs(x[1])


class KirbyController:
    def __init__(self, first_name: str = "Kirby"):
        self.characters_no = None
        self.first_name: str = first_name
        self.map: torch.Tensor = torch.zeros((0,))
        self.transparent: torch.Tensor = torch.zeros((0,))
        self.terrain: dict = {}
        self.seen: torch.Tensor = torch.zeros((0,))
        self.menhir: tuple = (0, 0)
        self.prev_actions: list[int] = [7 for _ in range(5)]
        self.mist: set[tuple[int, int]] = set()
        self.found_menhir: bool = False
        self.weapon = Knife().description()

        self.consumables: set = set()
        self.loot: dict[tuple[int, int], WeaponDescription] = {}
        self.effects: set = set()
        self.trees: list = []

        self.characters: dict[str, ChampionDescription] = {}
        self.positions_to_characters: dict = {}
        self.characters_to_positions: dict = {}

        self.actor_A = ActorNet(action_size=POLICIES_NUM, input_size=24).to(device)
        self.actor_B = ActorNet(action_size=POLICIES_NUM, input_size=24).to(device)
        self.actor_A.eval()
        self.actor_B.eval()
        self.actor_B.load_state_dict(self.actor_A.state_dict())

        self.critic_A = CriticNet(input_size=24).to(device)
        self.critic_B = CriticNet(input_size=24).to(device)
        self.critic_B.load_state_dict(self.critic_A.state_dict())

        self.actor_loss_fn = ActorLoss()
        self.critic_loss_fn = torch.nn.MSELoss()

        self.actor_optimizer = torch.optim.AdamW(
            self.actor_A.parameters(), lr=ACTOR_LR_ARRAY[0]
        )
        self.critic_optimizer = torch.optim.AdamW(
            self.critic_A.parameters(), lr=CRITIC_LR_ARRAY[0]
        )

        self.time = 0

        self.actor_losses = []
        self.critic_losses = []
        self.actor_game_losses = []
        self.critic_game_losses = []
        self.scores = []
        self.times = []
        self.actions_count = []
        self.actions = np.zeros((POLICIES_NUM,))

        self.states: list[torch.Tensor] = []
        self.all_states = []
        self.rewards = []
        checkpoint = torch.load(
            os.path.join("gupb", "controller", "kirby_weights.pth"), weights_only=False
        )
        self.actor_A.load_state_dict(checkpoint["actor"])
        self.actor_B.load_state_dict(checkpoint["actor"])
        self.critic_A.load_state_dict(checkpoint["critic"])
        self.critic_B.load_state_dict(checkpoint["critic"])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KirbyController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def exploration_status(self):
        return self.seen.sum() / self.map.numel()

    def update_visible_items(
        self, visible_tiles: dict[Coords, TileDescription], my_position: tuple
    ):
        for coords, tile in visible_tiles.items():
            self.seen[coords] = 1

            if tile.type == "menhir":
                self.menhir = coords
                self.found_menhir = True
            elif coords == self.menhir and not self.found_menhir:
                self.random_menhir()

            if tile.type == "forest":
                self.trees.append(coords)

            if tile.consumable:
                self.consumables.add(coords)
            else:
                self.consumables.discard(coords)

            if tile.loot:
                self.loot[coords] = tile.loot
            elif coords in self.loot:
                self.loot.pop(coords)

            if tile.effects:
                self.effects.add(coords)
                if any(effect.type == "mist" for effect in tile.effects):
                    self.mist.add(coords)

            if tile.character is not None and coords != my_position:
                character_name = tile.character.controller_name
                self.characters[character_name] = tile.character
                old_pos = self.characters_to_positions.get(character_name, None)
                self.characters_to_positions[character_name] = coords
                if old_pos and old_pos != coords:
                    self.positions_to_characters.pop(old_pos, None)
                self.positions_to_characters[coords] = character_name
            elif (
                tile.character is None or coords == my_position
            ) and coords in self.positions_to_characters:
                character_name = self.positions_to_characters.pop(coords)
                self.characters_to_positions.pop(character_name)

    def random_menhir(self):
        self.menhir = (
            np.random.randint(self.map.shape[0] - 2 * MAP_PADDING),
            np.random.randint(self.map.shape[1] - 2 * MAP_PADDING),
        )
        while (
            not self.map[self.menhir[0] + MAP_PADDING, self.menhir[1] + MAP_PADDING]
            or self.seen[self.menhir]
            or self.menhir in self.mist
        ):
            self.menhir = (
                np.random.randint(self.map.shape[0] - 2 * MAP_PADDING),
                np.random.randint(self.map.shape[1] - 2 * MAP_PADDING),
            )

    def a_star_setup(self):
        return (
            np.full(
                (
                    self.map.shape[0] - 2 * MAP_PADDING,
                    self.map.shape[1] - 2 * MAP_PADDING,
                ),
                fill_value=float("inf"),
            ),
            Queue(),
        )

    def travel(
        self, my_position: tuple[int, int], my_direction: Facing
    ) -> characters.Action:
        distances, queue = self.a_star_setup()
        distances[self.menhir] = 0
        queue.put((self.menhir, 0))
        return self.path_finding(queue, distances, my_position, my_direction)

    def hide(
        self, my_position: tuple[int, int], my_direction: Facing
    ) -> characters.Action:
        distances, queue = self.a_star_setup()
        for tree in self.trees:
            distances[tree] = 0
            queue.put((tree, 0))
        distances[self.menhir] = 1000
        queue.put((self.menhir, 1000))
        return self.path_finding(queue, distances, my_position, my_direction)

    def bigger_weapons(
        self, my_position: tuple[int, int], my_direction: Facing
    ) -> characters.Action:
        distances, queue = self.a_star_setup()
        for coord in self.loot.keys():
            weapon_value = weapons_hierarchy[self.loot[coord]]
            if (
                weapon_value >= weapons_hierarchy[self.weapon]
                and self.weapon.name != "scroll"
            ):
                distances[coord] = -weapon_value * 10
                queue.put((coord, -weapon_value * 10))

        distances[self.menhir] = 1000
        queue.put((self.menhir, 1000))

        return self.path_finding(queue, distances, my_position, my_direction)

    def get_consumables(
        self, my_position: tuple[int, int], my_direction: Facing
    ) -> characters.Action:
        distances, queue = self.a_star_setup()
        for consumable in self.consumables:
            distances[consumable] = 0
            queue.put((consumable, 0))
        distances[self.menhir] = 1000
        queue.put((self.menhir, 1000))
        return self.path_finding(queue, distances, my_position, my_direction)

    def attack(
        self, my_position: tuple[int, int], my_direction: Facing
    ) -> characters.Action:
        my_weapon_hits = weapons_names_dict[self.weapon].cut_positions(
            self.terrain, Coords(*my_position), my_direction
        )
        if any(i in my_weapon_hits for i in self.positions_to_characters.keys()):
            return characters.Action.ATTACK
        attacking_positions = []
        for character_position, attack_position in product(
            self.positions_to_characters.keys(), my_weapon_hits
        ):
            goal_position = (
                character_position[0] - attack_position[0] + my_position[0],
                character_position[1] - attack_position[1] + my_position[1],
            )
            if (
                0 < goal_position[0] < self.map.shape[0] - MAP_PADDING * 2
                and 0 < goal_position[1] < self.map.shape[1] - MAP_PADDING * 2
                and character_position not in self.trees
            ):
                attacking_positions.append(
                    goal_position
                )  # The position I need to be at in order to attack opponent

        distances, queue = self.a_star_setup()
        for coord in attacking_positions:
            distances[coord] = 0
            queue.put((coord, 0))
        distances[self.menhir] = 1000
        queue.put((self.menhir, 1000))
        return self.path_finding(queue, distances, my_position, my_direction)

    def reconnaissance(
        self,
        my_position: tuple[int, int],  # noqa
        my_direction: Facing,  # noqa
    ) -> characters.Action:
        return characters.Action.TURN_LEFT

    def run(self, my_position: tuple[int, int], my_direction: Facing):
        truncated_map = self.map[MAP_PADDING:-MAP_PADDING, MAP_PADDING:-MAP_PADDING]
        distances, queue = self.a_star_setup()
        hits_map = self.opponents_hit_dict()
        if not any([self.positions_to_characters, hits_map, self.effects]):
            distances[self.menhir] = 0
            queue.put((self.menhir, 0))
            self.path_finding(queue, distances, my_position, my_direction)

        for position in chain(
            self.positions_to_characters, hits_map.keys(), self.effects
        ):
            is_in = (
                0 < position[0] < truncated_map.shape[0]
                and 0 < position[1] < truncated_map.shape[1]
            )
            if is_in:
                distances[position] = 0
                queue.put((position, 0))

        while not queue.empty():
            tile, distance = queue.get()
            for dir_vector in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                next_tile = tile[0] + dir_vector[0], tile[1] + dir_vector[1]
                is_in = (
                    0 < next_tile[0] < truncated_map.shape[0]
                    and 0 < next_tile[1] < truncated_map.shape[1]
                )
                if (
                    is_in
                    and next_tile not in self.mist
                    and truncated_map[next_tile]
                    and distances[next_tile] > distance + 1
                ):
                    distances[next_tile] = distance + 1
                    queue.put((next_tile, distance + 1))
        next_action_id = np.nan_to_num(
            np.array(
                [
                    distances[i, j]
                    if 0 < i < truncated_map.shape[0] and 0 < j < truncated_map.shape[1]
                    else 0
                    for i, j in neighbourhood_4(my_position)
                ]
            ),
            posinf=0,
        ).argmax()

        if (
            distances[my_position]
            > distances[neighbourhood_4(my_position)[next_action_id]]
        ):
            return characters.Action.TURN_RIGHT
        else:
            direction_diff = next_action_id - directions_to_indices[my_direction]
            match (direction_diff + DIRECTIONS_NUM) % DIRECTIONS_NUM:
                case 0:
                    return characters.Action.STEP_FORWARD
                case 1:
                    return characters.Action.STEP_LEFT
                case 2:
                    return characters.Action.STEP_BACKWARD
                case 3:
                    return characters.Action.STEP_RIGHT

    def opponents_hit_dict(self):
        opponents_hits = [
            (coord, weapon_power(character.weapon))
            for character in self.characters.values()
            if character.controller_name in self.characters_to_positions
            for coord in weapons_names_dict[character.weapon].cut_positions(
                self.terrain,
                Coords(*self.characters_to_positions[character.controller_name]),
                character.facing,
            )
        ]
        opponents_hits_dict = defaultdict(lambda: 0)
        for coord, damage in opponents_hits:
            opponents_hits_dict[coord] += damage
        return opponents_hits_dict

    def path_finding(
        self,
        queue: Queue,
        distances: np.ndarray,
        my_position: tuple[int, int],
        my_direction: Facing,
        additional_impassable=None,
    ):
        truncated_map = self.map[MAP_PADDING:-MAP_PADDING, MAP_PADDING:-MAP_PADDING]
        hits_map = self.opponents_hit_dict()
        while not queue.empty():
            tile, distance = queue.get()
            for dir_vector in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                next_tile = tile[0] + dir_vector[0], tile[1] + dir_vector[1]
                is_in = (
                    0 < next_tile[0] < truncated_map.shape[0]
                    and 0 < next_tile[1] < truncated_map.shape[1]
                )
                next_tile_effect = 1000 if next_tile in self.effects else 1
                next_tile_effect += hits_map[next_tile] * 100
                if (
                    is_in
                    and next_tile not in self.mist
                    and truncated_map[next_tile]
                    and next_tile not in self.positions_to_characters
                    and distances[next_tile] > distance + next_tile_effect
                    and (
                        additional_impassable is None
                        or next_tile not in additional_impassable
                    )
                ):
                    distances[next_tile] = distance + next_tile_effect
                    queue.put((next_tile, distance + next_tile_effect))
        next_action_id = np.array(
            [
                distances[i, j]
                if 0 < i < truncated_map.shape[0] and 0 < j < truncated_map.shape[1]
                else float("inf")
                for i, j in neighbourhood_4(my_position)
            ]
        ).argmin()
        if distances[my_position] == 0:
            return characters.Action.TURN_LEFT
        else:
            direction_diff = next_action_id - directions_to_indices[my_direction]
            match (direction_diff + DIRECTIONS_NUM) % DIRECTIONS_NUM:
                case 0:
                    return characters.Action.STEP_FORWARD
                case 1:
                    return characters.Action.STEP_LEFT
                case 2:
                    return characters.Action.STEP_BACKWARD
                case 3:
                    return characters.Action.STEP_RIGHT

    def get_neighbourhood_from(
        self, my_position: tuple[int, int], my_direction: Facing, my_map: torch.Tensor
    ) -> torch.Tensor:
        neighbourhood = my_map[
            my_position[0] : my_position[0] + 2 * MAP_PADDING + 1,
            my_position[1] : my_position[1] + 2 * MAP_PADDING + 1,
        ]

        neighbourhood = directions_to_rotations[my_direction](neighbourhood)
        coords_list = [(i + 2, j + 2) for i, j in neighbourhood_coords_list]
        return torch.tensor([neighbourhood[coords] for coords in coords_list])

    def get_neighbourhood(
        self, my_position: tuple[int, int], my_direction: Facing
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        ##2##
        #212#
        21012
        #212#
        ##2##
        Używam takiego sąsiedztwa
        """
        neighbourhood = self.map[
            my_position[0] : my_position[0] + 2 * MAP_PADDING + 1,
            my_position[1] : my_position[1] + 2 * MAP_PADDING + 1,
        ]

        neighbourhood = directions_to_rotations[my_direction](neighbourhood)
        f1 = neighbourhood[1, 2]
        f2 = f1 and neighbourhood[0, 2]
        r1 = neighbourhood[2, 3]
        r2 = r1 and neighbourhood[2, 4]
        rf = neighbourhood[1, 3] and (f1 or r1)
        l1 = neighbourhood[2, 1]
        l2 = l1 and neighbourhood[2, 0]
        lf = neighbourhood[1, 1] and (f1 or l1)
        b1 = neighbourhood[3, 2]
        b2 = neighbourhood[4, 2] and b1
        lb = neighbourhood[3, 1] and (b1 or l1)
        rb = neighbourhood[3, 3] and (b1 or r1)
        neighbourhood = torch.tensor([f1, f2, l1, l2, lf, r1, r2, rf, b1, b2, lb, rb])
        return neighbourhood, f1

    def opponents_hits(
        self, opponents_hits: list[tuple[tuple[int, int], int]]
    ) -> tuple[float, float]:
        hit_effects = defaultdict(lambda: 0)
        for tile in opponents_hits:
            relative_coord = tile[0]
            if relative_coord in neighbourhood_coords_list:
                hit_effects[relative_coord] += tile[1]

        return sum(hit_effects[i] for i in neighbourhood_coords_list) / 40, hit_effects[
            (0, 0)
        ] / 8

    def analyse_knoledge(self, knowledge: characters.ChampionKnowledge):
        relative_coords = lambda x: dir_to_coords_change[my_direction](
            x[0] - knowledge.position.x, knowledge.position.y - x[1]
        )
        if self.time == 0:
            self.characters_no = knowledge.no_of_champions_alive
        my_position = knowledge.position
        my_tile: TileDescription = knowledge.visible_tiles[knowledge.position]
        my_effects = 1 if my_tile.effects else 0
        my_health = my_tile.character.health / 16

        my_direction = my_tile.character.facing

        self.weapon = my_tile.character.weapon
        my_weapon_hits = {
            i
            for i in weapons_names_dict[self.weapon].cut_positions(
                self.terrain, my_position, my_direction
            )
        }
        my_weapon_power = weapon_power(self.weapon)
        my_vector = torch.tensor(
            [
                my_health,
                my_effects,
                my_position[0] / (self.map.shape[0] - 2 * MAP_PADDING),
                my_position[1] / (self.map.shape[1] - 2 * MAP_PADDING),
                *directions_values[my_direction],
            ]
        )

        self.update_visible_items(knowledge.visible_tiles, my_position)

        closest_consumables = sum(
            1 / distance_x_y(relative_coords(i))
            for i in self.consumables
            if distance_x_y(relative_coords(i)) > 0
        )
        closest_effects = sum(
            1
            / (
                distance_x_y(relative_coords(i))
                if distance_x_y(relative_coords(i)) > 0
                else 0.4
            )
            for i in self.effects
        )
        closest_loot = sum(
            max(1, weapons_hierarchy[self.loot[i]] * 2)
            / (
                distance_x_y(relative_coords(i))
                if distance_x_y(relative_coords(i)) > 0
                else 0.4
            )
            for i in self.loot
        )
        closest_trees = sum(
            1
            / (
                distance_x_y(relative_coords(i))
                if distance_x_y(relative_coords(i)) > 0
                else 0.4
            )
            for i in self.trees
            if distance_x_y(relative_coords(i)) > 0
        )

        closest_characters = 0.0
        for i, (character_name, coords) in enumerate(
            self.characters_to_positions.items()
        ):
            character = self.characters[character_name]
            closest_characters += (
                max(1.0, weapons_hierarchy[character.weapon] * 2)
                * character.health
                / distance_x_y(relative_coords(coords))
                if distance_x_y(relative_coords(coords)) > 0
                else 0
            )
        attack_effects = (
            sum(
                [
                    my_weapon_power
                    for i in self.positions_to_characters.keys()
                    if i in my_weapon_hits
                ]
            )
            / 8
        )
        closest_mist = max(
            [1 / (distance_x_y(i) if distance_x_y(i) > 0 else 0.5) for i in self.mist]
            + [0]
        )
        opponents_hits: list[tuple[tuple[int, int], int]] = [
            (relative_coords(i), weapon_power(character.weapon))
            for character in self.characters.values()
            if character.controller_name in self.characters_to_positions
            for i in weapons_names_dict[character.weapon].cut_positions(
                self.terrain,
                Coords(*self.characters_to_positions[character.controller_name]),
                character.facing,
            )
        ]

        hits_sum_neighbourhood, hits_on_me = torch.tensor(
            self.opponents_hits(opponents_hits), dtype=torch.float32
        )

        neighbourhood, _ = self.get_neighbourhood(my_position, my_direction)

        local_exploration = self.get_neighbourhood_from(
            my_position, my_direction, self.seen
        ).sum()
        is_hidden = knowledge.visible_tiles[my_position].type == "forest"
        meta = torch.tensor(
            [
                knowledge.no_of_champions_alive / self.characters_no,
                self.found_menhir,
                self.exploration_status(),
                self.time,
                attack_effects,
                self.map.shape[0],
                self.map.shape[1],
                closest_consumables,
                np.sqrt(closest_loot),
                np.sqrt(closest_effects),
                np.sqrt(closest_trees),
                hits_on_me,
                hits_sum_neighbourhood,
                local_exploration,
                neighbourhood.sum(),
                np.sqrt(closest_characters),
                is_hidden,
                closest_mist,
            ]
        )
        result_vector = torch.hstack(
            [
                my_vector,  # 6
                meta,  # 18
            ],  # 24
        )
        return result_vector.type(torch.float32), attack_effects

    def normalize_state(self, state: torch.Tensor) -> torch.Tensor:
        avgs = torch.tensor(
            [
                5.4893e-01,
                6.6367e-03,
                4.0418e-01,
                4.3768e-01,
                4.8756e-01,
                5.0462e-01,
                6.5315e-01,
                6.0325e-01,
                4.4587e-01,
                2.9541e02,
                1.1319e-02,
                4.2241e01,
                4.2241e01,
                7.5589e-02,
                1.1823e00,
                6.6535e-01,
                4.9417e00,
                4.8999e-03,
                1.6028e-02,
                1.3070e01,
                9.0275e00,
                2.4509e00,
                5.3455e-02,
                1.6339e-01,
            ]
        )
        stds = torch.tensor(
            [
                2.2256e-01,
                8.1196e-02,
                2.2194e-01,
                2.2358e-01,
                4.9985e-01,
                4.9998e-01,
                1.7997e-01,
                4.8923e-01,
                1.8282e-01,
                2.0630e02,
                5.9607e-02,
                7.0683e00,
                7.0683e00,
                1.3641e-01,
                7.6855e-01,
                1.3493e00,
                5.4691e00,
                3.9776e-02,
                4.7499e-02,
                2.2869e00,
                2.1908e00,
                1.5901e00,
                2.2494e-01,
                4.9910e-01,
            ]
        )
        return (state - avgs) / stds

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        my_position = tuple(knowledge.position)
        my_tile: TileDescription = knowledge.visible_tiles[knowledge.position]
        my_direction: Facing = my_tile.character.facing
        policies: list[Callable[[tuple[int, int], Facing], characters.Action]] = [
            self.travel,
            self.run,
            self.hide,
            self.attack,
            self.bigger_weapons,
            self.get_consumables,
            self.reconnaissance,
        ]

        new_map, attack_effects = self.analyse_knoledge(knowledge)
        new_map = self.normalize_state(new_map)

        with torch.no_grad():
            policy_b = self.actor_B(
                new_map.reshape((1, -1)).to(device)
            )  # przewidujemy przyszłość

        probs = policy_b.cpu().detach().numpy()[0]

        probs /= probs.sum()
        choice_idx = np.random.choice(
            [i for i in range(POLICIES_NUM)],
            p=probs if self.states else None,
        )

        self.time += 1

        self.actions[choice_idx] += 1
        self.prev_actions.append(choice_idx)
        self.states.append(new_map)

        return policies[choice_idx](my_position, my_direction)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        arena = Arena.load(arena_description.name)
        self.terrain = arena.terrain
        self.map = torch.zeros(arena.size)
        self.transparent = torch.zeros(arena.size)

        self.time = 0

        self.consumables = set()
        self.loot = {}
        self.effects = set()
        self.trees = []

        self.characters = {}
        self.characters_to_positions = {}
        self.positions_to_characters = {}

        for coords, tile in self.terrain.items():
            self.map[coords] += int(tile.passable)
            self.transparent[coords] += int(tile.transparent)

        self.map = torch.tensor(
            np.pad(
                self.map,
                ((MAP_PADDING, MAP_PADDING), (MAP_PADDING, MAP_PADDING)),
                "constant",
                constant_values=(0, 0),
            )
        )

        self.transparent = torch.tensor(
            np.pad(
                self.transparent,
                ((MAP_PADDING, MAP_PADDING), (MAP_PADDING, MAP_PADDING)),
                "constant",
                constant_values=(0, 0),
            )
        )
        self.seen = torch.zeros_like(self.map)
        self.random_menhir()
        self.found_menhir = False
        self.weapon = Knife().description()
        self.mist = set()
        self.states = []

    @property
    def name(self) -> str:
        return f"{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KIRBY


POTENTIAL_CONTROLLERS = [
    KirbyController("Kirby"),
]
