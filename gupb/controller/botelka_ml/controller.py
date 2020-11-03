from pathfinding.core.grid import Grid

from gupb.controller.botelka_ml.brain import get_state, epsilon_greedy_action, init_q, save_q
from gupb.controller.botelka_ml.models import Wisdom
from gupb.controller.botelka_ml.rewards import calculate_reward
from gupb.model.arenas import ArenaDescription, Arena
from gupb.model.characters import Action, ChampionKnowledge, Tabard

LEARNING_RATE = 0.5  # (alpha)
DISCOUNT_FACTOR = 0.95  # (gamma)

MAP_TILES_COST = {
    'sea': 0,  # Sea - obstacle
    'wall': 0,  # Wall  - obstacle
    'bow': 1,  # Bow
    'sword': 4,  # Sword
    'axe': 4,  # Axe
    'amulet': 4,  # Amulet
    'land': 3,  # Land
    'knife': 10000,  # Knife - start weapon, we usually want to avoid it
}

# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BotElkaController:
    def __init__(self, first_name: str):
        self.q = init_q()

        self.first_name: str = first_name
        self.arena = None

        self.old_action = Action.DO_NOTHING
        self.old_state = (0, 0, 0, 0)

        self.wisdom = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BotElkaController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    @property
    def name(self) -> str:
        return f"BotElka<{self.first_name}>"

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.BLUE

    def reset(self, arena_description: ArenaDescription) -> None:
        self.arena = Arena.load(arena_description.name)
        self.arena.menhir_position = arena_description.menhir_position

        matrix = [[0] * self.arena.size[0]]* self.arena.size[1]
        for coords, tile in self.arena.terrain.items():
            x, y = coords
            matrix[x][y] = MAP_TILES_COST.get(tile.description().type, 0)
        grid = Grid(matrix=matrix)

        self.wisdom = Wisdom(self.arena, None, self.name, grid)
        save_q(self.q)

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        self.wisdom.next_knowledge(knowledge)
        wisdom = self.wisdom

        new_state = get_state(wisdom)

        new_action = epsilon_greedy_action(self.q, new_state)

        reward = calculate_reward(wisdom, self.old_action)

        learned_value = (reward + DISCOUNT_FACTOR * self.q[new_state, new_action])
        self.q[self.old_state, self.old_action] = (1 - LEARNING_RATE) * self.q[self.old_state, self.old_action] + LEARNING_RATE * learned_value

        self.old_action = new_action
        self.old_state = new_state

        return new_action
