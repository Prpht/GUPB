import os.path
import traceback
from collections import defaultdict
from itertools import chain
from queue import Queue

import numpy as np
import torch
from matplotlib import pyplot as plt
from gupb import controller
from gupb.controller.neural_networks import ActorCriticNet, ActorLoss
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena

from gupb.model.characters import Facing, ChampionDescription
from gupb.model.coordinates import Coords
from gupb.model.effects import Mist
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
]
ROUNDS_NO = 3001
EPSILON = 0.0
LR_ARRAY: np.ndarray[float] = 1e-5 * np.cumprod(np.full(shape=(ROUNDS_NO,), fill_value=0.9975))
BOTS_NO = 5

DISCOUNT_FACTOR_ARRAY = np.linspace(0.9, 0.9, ROUNDS_NO)
EPSILON_ARRAY = np.linspace(EPSILON, 0.00, ROUNDS_NO)
DISCOUNT_FACTOR = DISCOUNT_FACTOR_ARRAY[0]

weapons_dict = {
    Knife().description(): (0, 0, 0),
    Sword().description(): (0, 0, 1),
    WeaponDescription(name="bow_loaded"): (0, 1, 0),
    WeaponDescription(name="bow_unloaded"): (0, 1, 1),
    Axe().description(): (1, 0, 0),
    Amulet().description(): (1, 0, 1),
    Scroll().description(): (1, 1, 0),
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
directions_values_relative = {
    (Facing.UP, Facing.UP): (0, 0),
    (Facing.DOWN, Facing.UP): (1, 0),
    (Facing.LEFT, Facing.UP): (0, 1),
    (Facing.RIGHT, Facing.UP): (1, 1),
    (Facing.UP, Facing.DOWN): (1, 0),
    (Facing.DOWN, Facing.DOWN): (0, 0),
    (Facing.LEFT, Facing.DOWN): (1, 1),
    (Facing.RIGHT, Facing.DOWN): (0, 1),
    (Facing.UP, Facing.LEFT): (1, 1),
    (Facing.DOWN, Facing.LEFT): (0, 1),
    (Facing.LEFT, Facing.LEFT): (0, 0),
    (Facing.RIGHT, Facing.LEFT): (1, 0),
    (Facing.UP, Facing.RIGHT): (0, 1),
    (Facing.DOWN, Facing.RIGHT): (1, 1),
    (Facing.LEFT, Facing.RIGHT): (1, 0),
    (Facing.RIGHT, Facing.RIGHT): (0, 0),
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

directions_to_indices = {Facing.UP: 0,
                         Facing.LEFT: 1,
                         Facing.DOWN: 2,
                         Facing.RIGHT: 3
                         }
indices_to_directions = {val: key for key, val in directions_to_indices.items()}

device = "cuda" if torch.cuda.is_available() else "cpu"


def weapon_power(weapon_name):
    return getattr(weapons_names_dict[weapon_name].cut_effect(), "damage", 5)


class KirbyLearningController(controller.Controller):
    def __init__(self, first_name: str = "Kirby"):
        self.first_name: str = first_name
        self.map: torch.Tensor = torch.zeros((0,))
        self.transparent: torch.Tensor = torch.zeros((0,))
        self.terrain: dict = {}
        self.seen: torch.Tensor = torch.zeros((0,))
        self.menhir: tuple = (0, 0)
        self.prev_map = None
        self.prev_actions = []
        self.mist: np.ndarray = np.zeros((0,))
        self.found_menhir: bool = False

        self.consumables: set = set()
        self.loot: set = set()
        self.effects: set = set()
        self.trees: list = []

        self.characters: dict[str, ChampionDescription] = {}
        self.positions_to_characters: dict = {}
        self.characters_to_positions: dict = {}

        self.model_A = ActorCriticNet().to(device)
        self.model_B = ActorCriticNet().to(device)
        self.model_B.load_state_dict(self.model_A.state_dict())

        self.actor_loss_fn = ActorLoss()
        self.critic_loss_fn = torch.nn.L1Loss()
        self.optimizer = torch.optim.Adam(self.model_A.parameters(), lr=LR_ARRAY[0])

        self.time = 0

        self.losses = []
        self.game_losses = []
        self.game_rewards = []
        self.rewards = []
        self.scores = []
        self.times = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KirbyLearningController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def update_visible_items(self, visible_tiles: dict, my_position: tuple):
        for coords, tile in visible_tiles.items():
            self.seen[coords] = 1

            if tile.type == "menhir":
                self.menhir = coords
                self.found_menhir = True
            elif coords == self.menhir and not self.found_menhir:
                self.random_menhir()

            if tile.type == "forest":
                self.trees.append(coords)

            if tile.loot:
                self.loot.add(coords)
            else:
                self.loot.discard(coords)

            if tile.consumable:
                self.consumables.add(coords)
            else:
                self.consumables.discard(coords)

            if tile.effects:
                self.effects.add(coords)
                if any(isinstance(effect, Mist) for effect in tile.effects):
                    self.mist[coords] = 1

            if tile.character is not None and coords != my_position:
                character_name = tile.character.controller_name
                self.characters[character_name] = tile.character
                old_pos = self.characters_to_positions.get(character_name, None)
                self.characters_to_positions[character_name] = coords
                if old_pos and old_pos != coords:
                    self.positions_to_characters.pop(old_pos, None)
                self.positions_to_characters[coords] = character_name
            elif tile.character is None and coords in self.positions_to_characters:
                character_name = self.positions_to_characters.pop(coords)
                self.characters_to_positions.pop(character_name)

        # self.mist = tuple((i / mist_tiles if mist_tiles else 0) for i in mist_position)

    def random_menhir(self):
        self.menhir = (
            np.random.randint(self.map.shape[0] - 6),
            np.random.randint(self.map.shape[1] - 6),
        )
        while not self.map[self.menhir[0] + 3, self.menhir[1] + 3] or self.seen[self.menhir] or self.mist[self.menhir]:
            self.menhir = (
                np.random.randint(self.map.shape[0] - 6),
                np.random.randint(self.map.shape[1] - 6),
            )

    def travel(self, my_position: tuple[int, int], my_direction: Facing) -> characters.Action:
        distances = np.full((self.map.shape[0] - 6, self.map.shape[1] - 6, 4), fill_value=float("inf"))
        queue = Queue()
        for i in range(4):
            distances[(*self.menhir, i)] = 0
            queue.put((self.menhir, i, 0))
        return self.path_finding(queue, distances, my_position, my_direction)

    def hide(self, my_position: tuple[int, int], my_direction: Facing) -> characters.Action:
        distances = np.full((self.map.shape[0] - 6, self.map.shape[1] - 6, 4), fill_value=float("inf"))
        queue = Queue()
        for tree in self.trees:
            for i in range(4):
                distances[(*tree, i)] = 0
                queue.put((tree, i, 0))
        return self.path_finding(queue, distances, my_position, my_direction)

    def attack(self, my_position: tuple[int, int], my_direction: Facing) -> characters.Action:
        return characters.Action.ATTACK

    def run(self, my_position: tuple[int, int], my_direction: Facing):
        truncated_map = self.map[3: -3, 3: -3]
        distances = np.full((*truncated_map.shape, 4), fill_value=float("inf"))
        queue = Queue()
        hits_map = self.opponents_hit_dict()
        for position in chain(self.positions_to_characters, hits_map.keys(), self.effects):
            for i in range(4):
                is_in = 0 < position[0] < truncated_map.shape[0] and 0 < position[1] < truncated_map.shape[1]
                if is_in:
                    distances[(*position, i)] = 0
                    queue.put((position, i, 0))

        while not queue.empty():
            tile, direction, distance = queue.get()
            dir_vector = indices_to_directions[direction].value
            for dir_change, add_distance in zip((1, 3, 2), (1, 1, 2)):
                if distances[(*tile, (direction + dir_change) % 4)] > distance + add_distance:
                    distances[(*tile, (direction + dir_change) % 4)] = distance + add_distance
                    queue.put((tile, (direction + dir_change) % 4, distance + add_distance))


            next_tile = tile[0] + dir_vector[0], tile[1] + dir_vector[1]
            is_in = 0 < next_tile[0] < truncated_map.shape[0] and 0 < next_tile[1] < truncated_map.shape[1]

            if is_in and not self.mist[next_tile] and truncated_map[next_tile] and distances[
                (*next_tile, direction)] > distance + 1:
                distances[(*next_tile, direction)] = distance + 1
                queue.put((next_tile, direction, distance + 1))
        position_idx = (distances[my_position].argmin() - directions_to_indices[my_direction] + 4) % 4
        dir_vector = my_direction.value
        tile_in_front = my_position[0] + dir_vector[0], my_position[1] + dir_vector[1]
        is_in = 0 < tile_in_front[0] < truncated_map.shape[0] and 0 < tile_in_front[1] < truncated_map.shape[1]
        if position_idx == 0 and distances[(*tile_in_front, 0)] < float("inf") and is_in:
            return characters.Action.STEP_FORWARD
        elif position_idx == 2 or position_idx == 3:
            return characters.Action.TURN_RIGHT
        return characters.Action.TURN_LEFT

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

    def path_finding(self, queue: Queue, distances: np.ndarray, my_position: tuple[int, int], my_direction: Facing):
        truncated_map = self.map[3: -3, 3: -3]
        hits_map = self.opponents_hit_dict()
        while not queue.empty():
            tile, direction, distance = queue.get()
            dir_vector = indices_to_directions[direction].value
            for dir_change, add_distance in zip((1, 3, 2), (1, 1, 2)):
                if distances[(*tile, (direction + dir_change) % 4)] > distance + add_distance:
                    distances[(*tile, (direction + dir_change) % 4)] = distance + add_distance
                    queue.put((tile, (direction + dir_change) % 4, distance + add_distance))

            next_tile = tile[0] + dir_vector[0], tile[1] + dir_vector[1]
            next_tile_effect = (1000 if next_tile in self.effects else 1)
            next_tile_effect += hits_map[next_tile] * 100

            is_in = 0 < next_tile[0] < truncated_map.shape[0] and 0 < next_tile[1] < truncated_map.shape[1]
            if is_in and not self.mist[next_tile] and truncated_map[next_tile] and distances[
                (*next_tile, direction)] > distance + next_tile_effect:
                distances[(*next_tile, direction)] = distance + next_tile_effect
                queue.put((next_tile, direction, distance + 1))
        position_idx = (distances[my_position].argmin() - directions_to_indices[my_direction] + 4) % 4
        if distances[(*my_position, directions_to_indices[my_direction])] in [float("inf"), 0]:
            return characters.Action.TURN_LEFT
        if position_idx == 2:
            return characters.Action.STEP_FORWARD
        elif position_idx == 0 or position_idx == 3:
            return characters.Action.TURN_LEFT
        return characters.Action.TURN_RIGHT

    def get_transparent(
            self, my_position: tuple[int, int], my_direction: Facing
    ) -> torch.Tensor:
        neighbourhood = self.transparent[
                        my_position[0]: my_position[0] + 7, my_position[1]: my_position[1] + 7
                        ]

        neighbourhood = directions_to_rotations[my_direction](neighbourhood)

        coords_list = [(3, 3), (2, 3), (1, 3), (0, 3), (3, 4), (3, 5), (2, 4), (3, 2), (3, 1), (2, 2), (4, 3)]
        neighbourhood = torch.tensor([neighbourhood[coords] for coords in coords_list])
        return neighbourhood

    def get_neighbourhood(
            self, my_position: tuple[int, int], my_direction: Facing
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        ###3###
        ###2###
        ##313##
        #32023#
        ###3###
        #######
        #######

        Używam takiego sąsiedztwa
        """
        neighbourhood = self.map[
                        my_position[0]: my_position[0] + 7, my_position[1]: my_position[1] + 7
                        ]

        neighbourhood = directions_to_rotations[my_direction](neighbourhood)
        f = neighbourhood[2, 3]
        ff = f and neighbourhood[1, 3]
        fff = ff and neighbourhood[0, 3]
        r = neighbourhood[3, 4]
        rr = r and neighbourhood[3, 5]
        rf = neighbourhood[2, 4] and (f or r)
        l = neighbourhood[3, 2]
        ll = l and neighbourhood[3, 1]
        lf = neighbourhood[2, 2] and (f or l)
        b = neighbourhood[4, 3]
        neighbourhood = torch.tensor([f, ff, fff, l, ll, lf, r, rr, rf, b])
        return neighbourhood, f

    def opponents_hits_vector(
            self, opponents_hits: list[tuple[tuple[int, int], int]]
    ) -> list[int]:
        neighbourhood_hits = [
            (-3, 0),
            (-2, 0),
            (-1, 0),
            (-1, -1),
            (-1, 1),
            (0, -2),
            (0, -1),
            (0, 0),
            (0, 1),
            (0, 2),
            (1, 0),
        ]
        hit_effects = defaultdict(lambda: 0)
        for tile in opponents_hits:
            relative_coord = tile[0]
            if relative_coord in neighbourhood_hits:
                hit_effects[relative_coord] += tile[1]

        return [hit_effects[i] for i in neighbourhood_hits]

    def analyse_knoledge(self, knowledge: characters.ChampionKnowledge):
        relative_coords = lambda x: dir_to_coords_change[my_direction](
            x[0] - knowledge.position.x, knowledge.position.y - x[1]
        )
        scaled_coords = lambda x: (
            x[0] / self.map.shape[0] - 6,
            x[1] / self.map.shape[1] - 6,
        )
        distance_x_y = lambda x: abs(x[0]) + abs(x[1])

        my_position = knowledge.position
        my_tile: TileDescription = knowledge.visible_tiles[knowledge.position]
        my_effects = 1 if my_tile.effects else 0
        my_health = my_tile.character.health / 8

        my_direction = my_tile.character.facing

        my_weapon: WeaponDescription = my_tile.character.weapon
        my_weapon_hits = {
            relative_coords(i)
            for i in weapons_names_dict[my_weapon].cut_positions(
                self.terrain, my_position, my_direction
            )
        }
        my_weapon_power = weapon_power(my_weapon)
        my_vector = torch.tensor([my_health, my_effects])

        self.update_visible_items(knowledge.visible_tiles, my_position)
        closest_consumables = torch.zeros((20,))
        nonzero_consumables = torch.tensor(
            [
                scaled_coords(j)
                for j in sorted(
                [relative_coords(i) for i in self.consumables], key=distance_x_y
            )[:10]
            ]
        ).reshape(-1)
        closest_consumables[: len(nonzero_consumables)] = nonzero_consumables

        closest_loot = torch.zeros((20,))
        nonzero_loot = torch.tensor(
            [
                scaled_coords(j)
                for j in sorted(
                [relative_coords(i) for i in self.loot], key=distance_x_y
            )[:10]
            ]
        ).reshape(-1)
        closest_loot[: len(nonzero_loot)] = nonzero_loot

        closest_effects = torch.zeros((20,))
        effects_relative_coords = sorted(
            [relative_coords(i) for i in self.effects], key=distance_x_y
        )[:10]
        effects_relative_scaled_coords = [
            scaled_coords(j) for j in effects_relative_coords
        ]
        nonzero_effects = torch.tensor(effects_relative_scaled_coords).reshape(-1)
        closest_effects[: len(nonzero_effects)] = nonzero_effects

        effect_in_front = 1 if (-1, 0) in effects_relative_coords else 0

        characters_seen = []
        for i, (character_name, coords) in enumerate(
                self.characters_to_positions.items()
        ):
            character = self.characters[character_name]
            direction = directions_values_relative[(character.facing, my_direction)]
            characters_seen.append(
                [
                    *direction,  # 2
                    character.health / 8,  # 1
                    *relative_coords(coords),  # 2
                ]
            )
        characters_seen.sort(key=lambda x: distance_x_y(x[-3:]))
        attack_effects = sum(
            [
                my_weapon_power
                for i in self.positions_to_characters.keys()
                if relative_coords(i) in my_weapon_hits
            ]
        ) / 8
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

        hits_vector = torch.tensor(
            self.opponents_hits_vector(opponents_hits), dtype=torch.float32
        )

        characters_vector = torch.zeros((3 * 5,))
        characters_seen = torch.tensor(
            [scaled_coords(i) for i in characters_seen[:3]]
        ).reshape(-1)
        characters_vector[: len(characters_seen)] = characters_seen

        neighbourhood, can_go_forward = self.get_neighbourhood(
            my_position, my_direction
        )

        transparent = self.get_transparent(
            my_position, my_direction
        )
        menhir_coords = scaled_coords(relative_coords(self.menhir))
        meta = torch.tensor(
            [
                knowledge.no_of_champions_alive,
                *menhir_coords,
                self.seen.sum() / self.map.numel(),
                self.time,
                effect_in_front,
                attack_effects,
                # *scaled_coords(relative_coords(self.mist)),
            ]
        )
        result_vector = torch.hstack(
            [
                my_vector,  # 2
                closest_consumables,  # 20
                # closest_loot,  # 20
                closest_effects,  # 20
                characters_vector,  # 15
                neighbourhood,  # 10
                transparent,  # 11
                meta,  # 7
                hits_vector,  # 11
            ]
        )
        return (
            result_vector.reshape(1, -1).type(torch.float32),
            attack_effects
        )

    def learn(self, current_reward, expected_reward, policy_log):
        actor_loss = self.actor_loss_fn(
            current_reward, expected_reward.detach(), policy_log
        )
        critic_loss = self.critic_loss_fn(
            torch.tensor(current_reward).reshape(1, 1).to(device), expected_reward
        )

        self.optimizer.zero_grad()
        (actor_loss + critic_loss).backward()
        torch.nn.utils.clip_grad_norm_(self.model_A.parameters(), max_norm=0.5)
        self.optimizer.step()
        self.losses.append(critic_loss.item())
        tau = 0.1
        for target_param, param in zip(
                self.model_B.parameters(), self.model_A.parameters()
        ):
            target_param.data.copy_(tau * param.data + (1.0 - tau) * target_param.data)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:

        try:
            my_position = tuple(knowledge.position)
            my_tile: TileDescription = knowledge.visible_tiles[knowledge.position]
            my_direction: Facing = my_tile.character.facing
            policies = [self.travel, self.run, self.hide, self.attack]
            new_map, attack_effects = self.analyse_knoledge(knowledge)

            my_tile = knowledge.visible_tiles[knowledge.position]
            my_health = my_tile.character.health
            
            with torch.no_grad():
                policy_b, expected_value_b = self.model_B(new_map.to(device))  # przewidujemy przyszłość

            if self.prev_map is not None:
                policy_a, expected_value_a = self.model_A(
                    self.prev_map.to(device))  # przewidujemy teraźniejszość na podstawie przeszłości
                prev_policy_log = torch.log(policy_a[0, self.prev_actions[-1]])

                current_reward = (
                        DISCOUNT_FACTOR * expected_value_b[0, 0].detach()  # przyszłość
                        + my_health / 8  # teraźniejszość # [0 - 1]
                        + attack_effects * policy_a[0, 3]  # [0 - 0.075]
                )

                self.learn(current_reward, expected_value_a, prev_policy_log)
                self.rewards.append(current_reward.detach().cpu().numpy())

            epsilon_greedy_probs = (
                    np.ones((4,)) / 4 * EPSILON
                    + (1 - EPSILON) * policy_b.cpu().detach().numpy()[0]
            )
            epsilon_greedy_probs /= epsilon_greedy_probs.sum()
            choice_idx = np.random.choice(
                [0, 1, 2, 3],
                p=epsilon_greedy_probs if self.prev_map is not None else None,
            )

            self.time += 1
            self.prev_map = new_map.clone()
            self.prev_actions.append(choice_idx)

            return policies[choice_idx](my_position, my_direction)
            # return POSSIBLE_ACTIONS[choice_idx]
        except Exception:
            print(traceback.print_exc())

    def praise(self, score: int) -> None:
        self.scores.append(score)
        self.times.append(self.time)
        if score < BOTS_NO:
            policy_a, expected_value_a = self.model_A(self.prev_map.to(device))
            prev_policy_log = torch.log(policy_a[0, self.prev_actions[-1]])
            self.learn(0, expected_value_a,
                       prev_policy_log)

    def log_progress(self, game_no):
        rewards = [i - 3 for i in self.scores]
        last_50_cumsum = [
            sum(rewards[i - 50: i + 1]) / min(i + 1, 50)
            for i in range(20, len(rewards))
        ]
        last_50_times = [
            sum(self.times[i - 50: i + 1]) / min(i + 1, 50)
            for i in range(20, len(self.times))
        ]
        fig, ax = plt.subplots(2, 2, figsize=(10, 6))
        ax[0, 0].plot(
            [i for i, _ in enumerate(self.game_losses)],
            [np.log(i) for i in self.game_losses],
        )
        ax[0, 1].plot(
            [i for i in range(20, len(rewards))],
            last_50_cumsum,
            color="orange",
        )
        ax[1, 0].plot(
            [i for i, _ in enumerate(self.game_rewards)],
            self.game_rewards,
            color="purple",
        )

        ax[1, 1].plot(
            [i for i in range(20, len(self.times))],
            last_50_times,
            color="green",
        )
        plt.show()
        plt.savefig(os.path.join("plots", f"all_rounds_{game_no}.png"))

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:

        global DISCOUNT_FACTOR, EPSILON
        DISCOUNT_FACTOR = DISCOUNT_FACTOR_ARRAY[game_no]
        EPSILON = EPSILON_ARRAY[game_no]
        if game_no == 0:
            if os.path.exists("best_weights.pth"):
                checkpoint = torch.load("best_weights.pth", weights_only=True)
                self.model_A.load_state_dict(checkpoint["model"])
                self.model_B.load_state_dict(self.model_A.state_dict())
                self.optimizer.load_state_dict(checkpoint["optimizer"])

        if game_no > 0:
            for g in self.optimizer.param_groups:
                g["lr"] = LR_ARRAY[game_no]
            self.game_losses.append(sum(self.losses) / len(self.losses))
            self.game_rewards.append(sum(self.rewards) / len(self.rewards))
            self.rewards = []
        arena = Arena.load(arena_description.name)
        self.terrain = arena.terrain
        K = 50
        if game_no % K == 0 and game_no:
            self.log_progress(game_no)

            checkpoint = {
                "model": self.model_A.state_dict(),
                "optimizer": self.optimizer.state_dict(),
            }
            torch.save(checkpoint, os.path.join("weights", f"weights{game_no}.pth"))

        self.map = torch.zeros(arena.size)
        self.transparent = torch.zeros(arena.size)
        self.seen = torch.zeros(arena.size)
        self.time = 0

        self.consumables: set = set()
        self.loot: set = set()
        self.effects: set = set()
        self.trees = []

        self.characters = {}
        self.characters_to_positions = {}
        self.positions_to_characters = {}

        for coords, tile in self.terrain.items():
            self.map[coords] += int(tile.passable)
            self.transparent[coords] += int(tile.transparent)

        self.mist = np.zeros_like(self.map)
        self.map = torch.tensor(
            np.pad(self.map, ((3, 3), (3, 3)), "constant", constant_values=(0, 0))
        )

        self.transparent = torch.tensor(
            np.pad(self.transparent, ((3, 3), (3, 3)), "constant", constant_values=(0, 0))
        )
        self.random_menhir()
        self.prev_map = None
        self.found_menhir = False
        self.prev_actions = []

    @property
    def name(self) -> str:
        return f"{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KIRBY


POTENTIAL_CONTROLLERS = [
    KirbyLearningController("Kirby"),
]
