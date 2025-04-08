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
EPSILON_BEGIN = 0.5
EPSILON_END = 0.15
EPSILON = 0.15  # EPSILON_BEGIN
weapons_dict = {
    Knife().description(): (0, 0, 0),
    Sword().description(): (0, 0, 1),
    WeaponDescription(name="bow_loaded"): (0, 1, 0),
    WeaponDescription(name="bow_unloaded"): (0, 1, 1),
    Axe().description(): (1, 0, 0),
    Amulet().description(): (1, 0, 1),
    Scroll().description(): (1, 1, 0),
}
directions_values = {
    Facing.UP: (0, 0),
    Facing.DOWN: (0, 1),
    Facing.LEFT: (1, 0),
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

device = "cuda" if torch.cuda.is_available() else "cpu"


class KirbyController(controller.Controller):
    def __init__(self, first_name: str = "Kirby"):
        self.first_name: str = first_name
        self.map: torch.Tensor = torch.zeros((0,))
        self.menhir: tuple = (0, 0)
        self.prev_map = None
        self.prev_action = None

        self.consumables: set() = set()
        self.loot: set() = set()
        self.effects: set() = set()

        self.characters: dict = {}
        self.positions_to_characters: dict = {}
        self.characters_to_positions: dict = {}

        self.model_A = Net().to(device)
        self.loss_fn = torch.nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model_A.parameters(), lr=1.0e-7)
        self.time = 0
        self.max_bots_no = 0

        self.losses = []
        self.game_losses = []
        self.averaged_results = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KirbyController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def analyse_knoledge(self, knowledge: characters.ChampionKnowledge):
        self.max_bots_no = max(self.max_bots_no, knowledge.no_of_champions_alive)
        my_position = knowledge.position
        my_tile = knowledge.visible_tiles[knowledge.position]
        my_health = my_tile.character.health
        # print(my_health)
        my_direction = directions_values[my_tile.character.facing]

        my_weapon = weapons_dict[my_tile.character.weapon]
        my_vector = torch.tensor([*my_weapon, *my_direction, my_health, 1])
        relative_coords = lambda x: dir_to_coords_change[my_tile.character.facing](
            x[0] - knowledge.position.x, knowledge.position.y - x[1]
        )
        # distance = lambda x: x[1]  # distance in theta, r coords
        distance = lambda x: abs(x[0]) + abs(x[1])  # distance in relative x, y coords
        # euclidean_distance = lambda x: np.sqrt(x[0] ** 2 + x[1] ** 2)
        # cosine_r_coords = lambda x: (x[0] / euclidean_distance(x) if x[0] else 0, abs(x[0]) + abs(x[1]))

        for coords, tile in knowledge.visible_tiles.items():
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

            if tile.character and coords != knowledge.position:
                character_name = tile.character.controller_name
                self.characters[character_name] = tile.character
                old_pos = self.characters_to_positions.get(character_name, None)
                # print('#', old_pos, self.time)
                # print('$', coords, self.time)
                self.characters_to_positions[character_name] = coords
                if old_pos and old_pos != coords:
                    # BUG???
                    self.positions_to_characters.pop(old_pos, None)
                self.positions_to_characters[coords] = character_name
            elif tile.character is None and coords in self.positions_to_characters:
                character_name = self.positions_to_characters.pop(coords)
                self.characters_to_positions.pop(character_name)

        closest_consumables = torch.zeros((20,))
        nonzero_consumables = torch.tensor(
            sorted([relative_coords(i) for i in self.consumables], key=distance)[:10]
        ).reshape(-1)
        closest_consumables[: len(nonzero_consumables)] = nonzero_consumables

        closest_loot = torch.zeros((20,))
        nonzero_loot = torch.tensor(
            sorted([relative_coords(i) for i in self.loot], key=distance)[:10]
        ).reshape(-1)
        closest_loot[: len(nonzero_loot)] = nonzero_loot

        closest_effects = torch.zeros((20,))
        nonzero_effects = torch.tensor(
            sorted([relative_coords(i) for i in self.effects], key=distance)[:10]
        ).reshape(-1)
        closest_effects[: len(nonzero_effects)] = nonzero_effects

        characters_seen = []
        for i, (character_name, coords) in enumerate(
                self.characters_to_positions.items()
        ):
            character = self.characters[character_name]
            direction = directions_values[character.facing]
            weapon = character.weapon
            characters_seen.append(
                [
                    *weapons_dict[weapon],
                    *direction,
                    character.health,
                    *relative_coords(coords),
                ]
            )

        characters_vector = torch.zeros(((self.max_bots_no - 1) * 8,))
        characters_seen = torch.tensor(characters_seen).reshape(-1)
        characters_vector[: len(characters_seen)] = characters_seen

        neighbourhood = self.map[
                        my_position[0]: my_position[0] + 3, my_position[1]: my_position[1] + 3
                        ]
        neighbourhood = directions_to_rotations[my_tile.character.facing](
            neighbourhood
        ).reshape(-1)
        meta = torch.tensor(
            [
                knowledge.no_of_champions_alive,
                *relative_coords(
                    self.menhir if self.menhir != (0, 0) else knowledge.position
                ),
            ]
        )
        result_vector = torch.hstack(
            [
                my_vector,
                closest_consumables,
                closest_loot,
                closest_effects,
                characters_vector,
                neighbourhood,
                meta,
            ]
        )
        return result_vector.reshape(1, -1).type(torch.float32)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        my_tile = knowledge.visible_tiles[knowledge.position]
        my_health = my_tile.character.health
        new_map = self.analyse_knoledge(knowledge)
        with torch.no_grad():
            Q = self.model_A(new_map.to(device))

        if self.prev_map is not None:
            expected_reward = self.model_A(self.prev_map.to(device))[
                0, self.prev_action
            ]
            current_reward = max(
                0.9 * Q[0].max().detach()
                + my_health,
                #  - 0.1 * sum(c.health for c in self.characters.values()),
                0,
            )
            reward = (current_reward - expected_reward.detach()).to(device)
            loss = self.loss_fn(expected_reward, reward)
            self.losses.append(loss.item())
            torch.cuda.empty_cache()
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

        if np.random.random() > EPSILON:
            choice_idx = Q[0].argmax()
            choice = POSSIBLE_ACTIONS[choice_idx]
        else:
            choice_idx = np.random.choice([i for i, _ in enumerate(POSSIBLE_ACTIONS)])
            choice = POSSIBLE_ACTIONS[choice_idx]

        self.time += 1
        self.prev_map = new_map.clone()
        self.prev_action = choice_idx

        return choice

    def praise(self, score: int) -> None:
        if score < self.max_bots_no:
            expected_reward = self.model_A(self.prev_map.to(device))[
                0, self.prev_action
            ]
            reward = (- expected_reward.detach()).to(device)
            loss = self.loss_fn(expected_reward, reward)
            self.losses.append(loss.item())
            torch.cuda.empty_cache()
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        global EPSILON
        """EPSILON = EPSILON_BEGIN * (1 - (game_no / 3001)) + EPSILON_END * (
                game_no / 3001
        )"""
        # torch.autograd.set_detect_anomaly(True)
        # print(self.characters_to_positions)
        if os.path.exists("best_weights.pth"):
            checkpoint = torch.load("best_weights.pth", weights_only=True)
            self.model_A.load_state_dict(checkpoint["model"])
            self.optimizer.load_state_dict(checkpoint["optimizer"])
        if game_no > 0:
            pass
            self.game_losses.append(sum(self.losses) / len(self.losses))
        arena = Arena.load(arena_description.name)
        terrain = arena.terrain
        K = 50
        if game_no % K == 0 and game_no:
            plt.plot(
                [i for i, _ in enumerate(self.game_losses)],
                [np.log(i) for i in self.game_losses],
            )
            plt.savefig(os.path.join("plots", f"all_rounds_{game_no}_t.png"))
            plt.show()
            checkpoint = {
                "model": self.model_A.state_dict(),
                "optimizer": self.optimizer.state_dict(),
            }
            torch.save(checkpoint, "weights.pth")
            self.averaged_results.append(sum(self.game_losses[-K:]))
            plt.bar(
                [i for i, _ in enumerate(self.averaged_results)],
                [np.log(i) for i in self.averaged_results],
            )
            plt.savefig(os.path.join("plots", f"50_rounds_{game_no}_t.png"))
            plt.show()

        self.map = torch.zeros(arena.size)
        self.time = 0
        self.max_bots_no = arena.no_of_champions_alive

        self.consumables: set() = set()
        self.loot: set() = set()
        self.effects: set() = set()

        self.characters = {}
        self.characters_to_positions = {}
        self.positions_to_characters = {}

        self.menhir = (0, 0)

        for coords, tile in terrain.items():
            self.map[coords] += int(tile.passable)
        self.map = torch.tensor(np.pad(
            self.map, ((1, 1), (1, 1)), "constant", constant_values=(0, 0)
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
    KirbyController("Kirby"),
]
