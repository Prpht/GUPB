import os.path
import numpy as np
import torch
from matplotlib import pyplot as plt
from gupb import controller
from gupb.controller.DDQN import Net
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena

from gupb.model.characters import Facing
from gupb.model.tiles import Menhir
from gupb.model.weapons import Knife, Sword, Axe, Amulet, Scroll, WeaponDescription

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

        self.model_A = Net().to(device)
        self.model_B = Net().to(device)
        self.model_B.load_state_dict(self.model_A.state_dict())

        self.loss_fn = torch.nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model_A.parameters(), lr=LR)
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

    def analyse_knoledge(self, knowledge: characters.ChampionKnowledge):
        relative_coords = lambda x: dir_to_coords_change[my_direction](
            x[0] - knowledge.position.x, knowledge.position.y - x[1]
        )
        # distance_x_y_r = lambda x: x[-1]  # distance in theta, r coords
        distance_x_y = lambda x: abs(x[0]) + abs(x[1])  # distance in relative x, y coords
        # euclidean_distance = lambda x: np.sqrt(x[0] ** 2 + x[1] ** 2)
        x_y_r_coords = lambda x: (np.sign(x[0]),
                                  np.sign(x[1]),
                                  distance_x_y(x))

        my_position = knowledge.position
        my_tile = knowledge.visible_tiles[knowledge.position]
        my_effects = 1 if my_tile.effects else 0
        my_health = my_tile.character.health

        my_direction = my_tile.character.facing

        my_weapon = weapons_dict[my_tile.character.weapon]
        my_vector = torch.tensor([*my_weapon, my_health, my_effects])

        self.update_visible_items(knowledge.visible_tiles, my_position)
        closest_consumables = torch.zeros((20,))
        nonzero_consumables = torch.tensor(
            sorted([relative_coords(i) for i in self.consumables], key=distance_x_y)[:10]
        ).reshape(-1)
        closest_consumables[: len(nonzero_consumables)] = nonzero_consumables

        closest_loot = torch.zeros((20,))
        nonzero_loot = torch.tensor(
            sorted([relative_coords(i) for i in self.loot], key=distance_x_y)[:10]
        ).reshape(-1)
        closest_loot[: len(nonzero_loot)] = nonzero_loot

        closest_effects = torch.zeros((20,))
        effects_relative_coords = sorted([relative_coords(i) for i in self.effects], key=distance_x_y)[:10]
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

        characters_vector = torch.zeros((3 * 8,))
        characters_seen = torch.tensor(characters_seen[:3]).reshape(-1)
        characters_vector[: len(characters_seen)] = characters_seen

        neighbourhood = self.map[
                        my_position[0]: my_position[0] + 7, my_position[1]: my_position[1] + 7
                        ]

        neighbourhood = directions_to_rotations[my_direction](
            neighbourhood
        ).reshape(-1)
        neighbourhood = torch.tensor([neighbourhood[i] for i in (3, 10, 16, 17, 18, 22, 23, 25, 26, 31)])
        """
        ###3###
        ###2###
        ##313##
        #32023#
        ###3###
        #######
        #######
        """
        meta = torch.tensor(
            [
                knowledge.no_of_champions_alive,
                *relative_coords(
                    self.menhir if self.menhir != (0, 0) else knowledge.position
                ),
                self.seen.sum() / self.map.numel(),
                self.time,
                effect_in_front
            ]
        )
        result_vector = torch.hstack(
            [
                my_vector,  # 4
                closest_consumables,  # 20
                # closest_loot,  # 20
                closest_effects,  # 20
                characters_vector,  # 24
                neighbourhood,  # 10
                meta,  # 7
            ]
        )
        return result_vector.reshape(1, -1).type(torch.float32), neighbourhood[1]

    def get_random_action(self, can_move_forward):
        choice_idx = np.random.choice([i for i, _ in enumerate(POSSIBLE_ACTIONS)])
        while not can_move_forward and choice_idx == 2:
            choice_idx = np.random.choice([i for i, _ in enumerate(POSSIBLE_ACTIONS)])
        choice = POSSIBLE_ACTIONS[choice_idx]
        return choice_idx, choice

    def get_best_action(self, can_move_forward, predicted_health):
        options = predicted_health[0].detach()
        if not can_move_forward:
            options[2] = 0
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
        new_map, can_move_forward = self.analyse_knoledge(knowledge)
        with torch.no_grad():
            predicted_health = self.model_B(new_map.to(device))
        if self.prev_map is not None:
            expected_reward = self.model_A(self.prev_map.to(device))[
                0, self.prev_action
            ]
            current_reward = max(
                DISCOUNT_FACTOR * predicted_health[0].max().detach()
                + my_health,
                # - 0.1 * sum(c.health for c in self.characters.values()),
                0,
            )
            self.learn(current_reward, expected_reward)

        if not can_move_forward and (predicted_health[0].detach().argmax() == 2):
            expected_reward = self.model_A(new_map.to(device))[0, 2]
            self.learn(0, expected_reward)

        if np.random.random() > EPSILON:
            choice_idx, choice = self.get_best_action(can_move_forward, predicted_health)
        else:
            choice_idx, choice = self.get_random_action(can_move_forward)

        self.time += 1
        self.prev_map = new_map.clone()
        self.prev_action = choice_idx

        return choice

    def praise(self, score: int) -> None:
        self.scores.append(score)
        if score < BOTS_NO:
            expected_reward = self.model_A(self.prev_map.to(device))[
                0, self.prev_action
            ]
            self.learn(0, expected_reward)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.model_B.load_state_dict(self.model_A.state_dict())
        global EPSILON, DISCOUNT_FACTOR
        EPSILON = EPSILON_BEGIN * (1 - (game_no / ROUNDS_NO)) + EPSILON_END * (
                game_no / ROUNDS_NO
        )
        DISCOUNT_FACTOR = 0.7 * (game_no / ROUNDS_NO)
        if game_no == 0:
            if os.path.exists("best_weights.pth"):
                checkpoint = torch.load("best_weights.pth", weights_only=True)
                self.model_A.load_state_dict(checkpoint["model"])
                self.optimizer.load_state_dict(checkpoint["optimizer"])
                for g in self.optimizer.param_groups:
                    g['lr'] = LR

        if game_no > 0:
            for g in self.optimizer.param_groups:
                g['lr'] *= LR_DECAY
            self.game_losses.append(sum(self.losses) / len(self.losses))
        arena = Arena.load(arena_description.name)
        terrain = arena.terrain
        K = 50
        if game_no % K == 0 and game_no:
            plt.plot(
                [i for i, _ in enumerate(self.game_losses)],
                [np.log(i) for i in self.game_losses],
            )
            plt.savefig(os.path.join("plots", f"all_rounds_{game_no}.png"))
            plt.show()
            plt.plot([i for i in range(len(self.scores))], np.cumsum([i-3 for i in self.scores]), color="orange")
            plt.show()
            checkpoint = {
                "model": self.model_A.state_dict(),
                "optimizer": self.optimizer.state_dict(),
            }
            torch.save(checkpoint, "weights.pth")

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

        for coords, tile in terrain.items():
            self.map[coords] += int(tile.passable)
        self.map = torch.tensor(np.pad(
            self.map, ((3, 3), (3, 3)), "constant", constant_values=(0, 0)
        ))
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
