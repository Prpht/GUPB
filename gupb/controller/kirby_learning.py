import os.path
import numpy as np
import torch
from matplotlib import pyplot as plt
from gupb import controller
from gupb.controller.neural_networks import Net
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena

from gupb.model.characters import Facing
from gupb.model.tiles import Menhir
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
LR_DECAY = 0.9995
EPSILON_BEGIN = 1
EPSILON_END = 0.4
BOTS_NO = 5
EPSILON = EPSILON_BEGIN
DISCOUNT_FACTOR = 0

LR = 5e-6
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

device = "cuda" if torch.cuda.is_available() else "cpu"


class KirbyLearningController(controller.Controller):
    def __init__(self, first_name: str = "Kirby"):
        self.first_name: str = first_name
        self.map: torch.Tensor = torch.zeros((0,))
        self.terrain: dict = {}
        self.seen: torch.Tensor = torch.zeros((0,))
        self.menhir: tuple = (0, 0)
        self.prev_map = None
        self.prev_action = None

        self.consumables: set = set()
        self.loot: set = set()
        self.effects: set = set()

        self.characters: dict = {}
        self.positions_to_characters: dict = {}
        self.characters_to_positions: dict = {}

        self.net_A = Net().to(device)
        self.net_B = Net().to(device)
        self.net_B.load_state_dict(self.net_A.state_dict())

        self.loss_fn = torch.nn.L1Loss()
        self.optimizer = torch.optim.Adam(self.net_A.parameters(), lr=LR)
        self.time = 0

        self.losses = []
        self.game_losses = []
        self.scores = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KirbyLearningController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def update_visible_items(self, visible_tiles: dict, my_position: tuple):
        for coords, tile in visible_tiles.items():
            self.seen[coords] = 1
            if isinstance(tile, Menhir):
                self.menhir = coords

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

            if tile.character and coords != my_position:
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
            my_position[0] : my_position[0] + 7, my_position[1] : my_position[1] + 7
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

    def analyse_knoledge(self, knowledge: characters.ChampionKnowledge):
        relative_coords = lambda x: dir_to_coords_change[my_direction](
            x[0] - knowledge.position.x, knowledge.position.y - x[1]
        )
        # distance_x_y_r = lambda x: x[-1]  # distance in theta, r coords
        distance_x_y = lambda x: abs(x[0]) + abs(
            x[1]
        )  # distance in relative x, y coords
        # euclidean_distance = lambda x: np.sqrt(x[0] ** 2 + x[1] ** 2)

        my_position = knowledge.position
        my_tile = knowledge.visible_tiles[knowledge.position]
        my_effects = 1 if my_tile.effects else 0
        my_health = my_tile.character.health

        my_direction = my_tile.character.facing

        my_weapon: WeaponDescription = my_tile.character.weapon
        my_weapon_hits = {
            relative_coords(i)
            for i in weapons_names_dict[my_weapon].cut_positions(
                self.terrain, my_position, my_direction
            )
        }
        my_weapon_effect = weapons_names_dict[my_weapon].cut_effect()
        my_weapon_power = getattr(my_weapon_effect, "damage", 5)
        my_vector = torch.tensor([my_health, my_effects])

        self.update_visible_items(knowledge.visible_tiles, my_position)
        closest_consumables = torch.zeros((20,))
        nonzero_consumables = torch.tensor(
            sorted([relative_coords(i) for i in self.consumables], key=distance_x_y)[
                :10
            ]
        ).reshape(-1)
        closest_consumables[: len(nonzero_consumables)] = nonzero_consumables

        closest_loot = torch.zeros((20,))
        nonzero_loot = torch.tensor(
            sorted([relative_coords(i) for i in self.loot], key=distance_x_y)[:10]
        ).reshape(-1)
        closest_loot[: len(nonzero_loot)] = nonzero_loot

        closest_effects = torch.zeros((20,))
        effects_relative_coords = sorted(
            [relative_coords(i) for i in self.effects], key=distance_x_y
        )[:10]
        nonzero_effects = torch.tensor(effects_relative_coords).reshape(-1)
        closest_effects[: len(nonzero_effects)] = nonzero_effects

        effect_in_front = 1 if (-1, 0) in effects_relative_coords else 0

        characters_seen = []
        for i, (character_name, coords) in enumerate(
            self.characters_to_positions.items()
        ):
            character = self.characters[character_name]
            direction = directions_values_relative[(character.facing, my_direction)]
            weapon = character.weapon
            characters_seen.append(
                [
                    *weapons_dict[weapon],  # 3
                    *direction,  # 2
                    character.health,  # 1
                    *relative_coords(coords),  # 2
                ]
            )
        characters_seen.sort(key=lambda x: distance_x_y(x[-3:]))
        attack_effects = sum(
            [
                relative_coords(i) * my_weapon_power
                for i in self.positions_to_characters.keys()
                if relative_coords(i) in my_weapon_hits
            ]
        )

        characters_vector = torch.zeros((3 * 8,))
        characters_seen = torch.tensor(characters_seen[:3]).reshape(-1)
        characters_vector[: len(characters_seen)] = characters_seen

        neighbourhood, can_go_forward = self.get_neighbourhood(
            my_position, my_direction
        )
        meta = torch.tensor(
            [
                knowledge.no_of_champions_alive,
                *relative_coords(
                    self.menhir if self.menhir != (0, 0) else knowledge.position
                ),
                self.seen.sum() / self.map.numel(),
                self.time,
                effect_in_front,
                attack_effects,
            ]
        )
        result_vector = torch.hstack(
            [
                my_vector,  # 2
                closest_consumables,  # 20
                # closest_loot,  # 20
                closest_effects,  # 20
                characters_vector,  # 24
                neighbourhood,  # 10
                meta,  # 7
            ]
        )
        return (
            result_vector.reshape(1, -1).type(torch.float32),
            can_go_forward,
            attack_effects,
        )

    def get_random_action(self, can_move_forward, can_attack):
        choice_idx = np.random.choice([i for i, _ in enumerate(POSSIBLE_ACTIONS)])
        while (
            not can_move_forward
            and choice_idx == 2
            or not can_attack
            and choice_idx == 3
        ):
            choice_idx = np.random.choice([i for i, _ in enumerate(POSSIBLE_ACTIONS)])
        choice = POSSIBLE_ACTIONS[choice_idx]
        return choice_idx, choice

    def get_best_action(self, can_move_forward, predicted_health, can_attack):
        options = predicted_health[0].detach()
        if not can_move_forward:
            options[2] = 0
        if not can_attack:
            options[3] = 0
        choice_idx = options.argmax()
        choice = POSSIBLE_ACTIONS[choice_idx]
        return choice_idx, choice

    def learn(self, current_reward, expected_reward):
        reward = (current_reward - expected_reward.detach()).to(device)
        loss = self.loss_fn(expected_reward, reward)
        self.losses.append(loss.item())
        torch.cuda.empty_cache()
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        my_tile = knowledge.visible_tiles[knowledge.position]
        my_health = my_tile.character.health
        new_map, can_move_forward, attack_effects = self.analyse_knoledge(knowledge)
        try:
            with torch.no_grad():
                predicted_health = self.net_B(new_map.to(device))
        except Exception as e:
            print(e)

        would_attack = predicted_health[0].detach().argmax() == 3
        would_go_forward = predicted_health[0].detach().argmax() == 2

        if not can_move_forward and would_go_forward:
            expected_reward = self.net_A(new_map.to(device))[0, 2]
            self.learn(0, expected_reward)

        elif attack_effects == 0 and would_attack:
            expected_reward = self.net_A(new_map.to(device))[0, 3]
            self.learn(0, expected_reward)

        elif self.prev_map is not None:
            expected_reward = self.net_A(self.prev_map.to(device))[0, self.prev_action]
            current_reward = max(
                DISCOUNT_FACTOR * predicted_health[0].max().detach()
                + my_health
                + 0.1 * attack_effects * int(would_attack),
                0,
            )
            self.learn(current_reward, expected_reward)

        if np.random.random() > EPSILON:
            choice_idx, choice = self.get_best_action(
                can_move_forward, predicted_health, attack_effects > 0
            )
        else:
            choice_idx, choice = self.get_random_action(
                can_move_forward, attack_effects > 0
            )

        self.time += 1
        self.prev_map = new_map.clone()
        self.prev_action = choice_idx

        return choice

    def praise(self, score: int) -> None:
        self.scores.append(score)
        if score < BOTS_NO:
            predicted_health = self.net_A(self.prev_map.to(device))[0].argmax()

            self.learn(0, predicted_health)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.net_B.load_state_dict(self.net_A.state_dict())
        global EPSILON, DISCOUNT_FACTOR
        EPSILON = EPSILON_BEGIN * (1 - (game_no / ROUNDS_NO)) + EPSILON_END * (
            game_no / ROUNDS_NO
        )
        DISCOUNT_FACTOR = 0.7  # * (game_no / ROUNDS_NO)
        if game_no == 0:
            if os.path.exists("best_weights.pth"):
                checkpoint = torch.load("best_weights.pth", weights_only=True)
                self.net_A.load_state_dict(checkpoint["model"])
                self.optimizer.load_state_dict(checkpoint["optimizer"])
                for g in self.optimizer.param_groups:
                    g["lr"] = LR

        if game_no > 0:
            for g in self.optimizer.param_groups:
                g["lr"] *= LR_DECAY
            self.game_losses.append(sum(self.losses) / len(self.losses))
        arena = Arena.load(arena_description.name)
        self.terrain = arena.terrain
        K = 50
        if game_no % K == 0 and game_no:
            plt.plot(
                [i for i, _ in enumerate(self.game_losses)],
                [np.log(i) for i in self.game_losses],
            )
            plt.savefig(os.path.join("plots", f"all_rounds_{game_no}.png"))
            plt.show()
            plt.plot(
                [i for i in range(len(self.scores))],
                np.cumsum([i - 3 for i in self.scores]),
                color="orange",
            )
            plt.show()
            checkpoint = {
                "model": self.net_A.state_dict(),
                "optimizer": self.optimizer.state_dict(),
            }
            torch.save(checkpoint, os.path.join("weights", f"weights{game_no}.pth"))

        self.map = torch.zeros(arena.size)
        self.seen = torch.zeros(arena.size)
        self.time = 0

        self.consumables: set = set()
        self.loot: set = set()
        self.effects: set = set()

        self.characters = {}
        self.characters_to_positions = {}
        self.positions_to_characters = {}

        self.menhir = (0, 0)

        for coords, tile in self.terrain.items():
            self.map[coords] += int(tile.passable)
        self.map = torch.tensor(
            np.pad(self.map, ((3, 3), (3, 3)), "constant", constant_values=(0, 0))
        )
        self.prev_map = None
        self.prev_action = None

    @property
    def name(self) -> str:
        return f"{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KIRBY


POTENTIAL_CONTROLLERS = [
    KirbyLearningController("Kirby"),
]
