import os.path

import numpy as np
import torch
from matplotlib import pyplot as plt
from gupb import controller
from gupb.controller.DDQN import Net
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena
from skimage.transform import resize

from gupb.model.characters import Facing
from gupb.model.weapons import Knife, Sword, Bow, Axe, Amulet, Scroll

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]
EPSILON = 0.00
weapons_power = {
    Knife().description(): 2,
    Sword().description(): 3,
    Bow().description(): 4,
    Axe().description(): 1,
    Amulet().description(): 5,
    Scroll().description(): 6,
}
directions_values = {Facing.UP: 0, Facing.DOWN: 1, Facing.LEFT: 2, Facing.RIGHT: 3}

device = "cuda" if torch.cuda.is_available() else "cpu"


class KirbyController(controller.Controller):
    def __init__(self, first_name: str = "Kirby"):
        self.first_name: str = first_name
        self.visited = np.zeros((0,))
        self.map: np.ndarray = np.zeros((0,))
        self.prev_map = None
        self.prev_action = None
        self.consumables: set() = set()
        self.characters: dict = {}
        self.positions_to_characters: dict = {}
        self.characters_to_positions: dict = {}
        self.weapon = None
        self.model_A = Net().to(device)
        self.loss_fn = torch.nn.MSELoss()
        self.optimizer = torch.optim.Adam(self.model_A.parameters(), lr=1.0e-4)
        self.time = 0
        self.prediction = None

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
        curr_map = np.zeros_like(self.map)
        my_tile = knowledge.visible_tiles[knowledge.position]
        my_health = my_tile.character.health
        direction = directions_values[my_tile.character.facing]

        my_weapon = my_tile.character.weapon
        curr_map[knowledge.position][0] += weapons_power[my_weapon]
        curr_map[knowledge.position][1] += direction
        curr_map[knowledge.position][2] += my_health

        for coords, tile in knowledge.visible_tiles.items():
            self.visited[coords] = 1
            if tile.loot:
                curr_map[coords][0] += 6
            if tile.effects:
                curr_map[coords][0] -= 12

            if tile.character and coords != knowledge.position:
                character_name = tile.character.controller_name
                self.characters[character_name] = tile.character
                old_pos = self.characters_to_positions.get(character_name, None)
                # print('#', old_pos, self.time)
                # print('$', coords, self.time)
                self.characters_to_positions[character_name] = coords
                if old_pos:
                    self.positions_to_characters.pop(old_pos)
                self.positions_to_characters[coords] = character_name
            if tile.character is None and coords in self.positions_to_characters:
                # print(">", coords, self.time)
                character_name = self.positions_to_characters.pop(coords)
                self.characters_to_positions.pop(character_name)
            if tile.effects:
                self.consumables.add(coords)
            else:
                self.consumables.discard(coords)

            for coord in self.consumables:
                curr_map[coord][2] += 6

        for character_name, coords in self.characters_to_positions.items():
            character = self.characters[character_name]
            direction = directions_values[character.facing]
            weapon = character.weapon
            curr_map[coords][0] -= weapons_power[weapon]
            curr_map[coords][1] += direction
            curr_map[coords][2] -= character.health

        curr_map += np.repeat(self.visited[:, :, None], 3, 2) + self.map
        new_map = resize(curr_map, (32, 32))
        # plt.imshow((new_map - new_map.min()) / (new_map.max() - new_map.min()))
        # plt.show()

        return torch.tensor(new_map, dtype=torch.float32).permute(2, 0, 1)[None, :, :, :]

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        my_tile = knowledge.visible_tiles[knowledge.position]
        my_health = my_tile.character.health

        new_map = self.analyse_knoledge(knowledge)
        with torch.no_grad():
            Q = self.model_A(new_map.to(device))

        if self.prev_map is not None:
            expected_reward = self.model_A(self.prev_map.to(device))[0, self.prev_action]
            reward = (
                    0.9 * Q[0].max().detach() + my_health - 0.1 * sum(c.health for c in self.characters.values()) - expected_reward.detach()
            ).to(device)
            loss = self.loss_fn(expected_reward, reward)
            self.losses.append(loss.item())
            torch.cuda.empty_cache()
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

        if np.random.random() > EPSILON:
            choice_idx = Q[0].argmax()
            predicted_health = Q[0].max().clone()
            choice = POSSIBLE_ACTIONS[choice_idx]
        else:
            choice_idx = np.random.choice([i for i, _ in enumerate(POSSIBLE_ACTIONS)])
            predicted_health = Q[0, choice_idx]
            choice = POSSIBLE_ACTIONS[choice_idx]
        self.time += 1
        self.prediction = predicted_health
        self.prev_map = new_map.clone()
        self.prev_action = choice_idx

        return choice

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        # torch.autograd.set_detect_anomaly(True)
        # print(self.characters_to_positions)
        self.best_result = float("inf")
        if os.path.exists('best_weights.pth'):
            checkpoint = torch.load('best_weights.pth', weights_only=True)
            self.model_A.load_state_dict(checkpoint['model'])
            self.optimizer.load_state_dict(checkpoint['optimizer'])
        if game_no > 0:
            pass
            self.game_losses.append(sum(self.losses) / len(self.losses))
        self.losses = []
        self.prediction = None
        arena = Arena.load(arena_description.name)
        terrain = arena.terrain
        K = 50
        if game_no % K == 0 and game_no:
            plt.plot([i for i, _ in enumerate(self.game_losses)], [np.log(i) for i in self.game_losses])
            plt.show()
            checkpoint = {
                "model": self.model_A.state_dict(),
                "optimizer": self.optimizer.state_dict(),
            }
            torch.save(checkpoint, 'weights.pth')
            self.averaged_results.append(sum(self.game_losses[-K:]))
            plt.bar([i for i, _ in enumerate(self.averaged_results)], self.averaged_results)
            plt.show()
            if self.averaged_results[-1] < self.best_result:
                self.best_result = self.averaged_results[-1]
                torch.save(checkpoint, 'best_weights.pth')
        self.map = np.zeros((*arena.size, 3))
        self.visited = np.zeros(arena.size)
        self.time = 0
        self.consumables: set() = set()
        self.characters = {}
        self.characters_to_positions = {}
        self.positions_to_characters = {}
        self.map[arena.menhir_position][0] = 7
        for coords, tile in terrain.items():
            self.map[coords][0] += 3 * int(tile.passable) + int(tile.transparent)
        self.prev_map = None
        self.prev_action = None

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KIRBY


POTENTIAL_CONTROLLERS = [
    KirbyController("Kirby"),
]
