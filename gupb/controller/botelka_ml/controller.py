from gupb.controller.botelka_ml.model import get_model
from gupb.controller.botelka_ml.rewards import calculate_reward
from gupb.controller.botelka_ml.wisdom import State, get_state
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
        self.first_name: str = first_name
        self.arena = None

        self.old_action = Action.DO_NOTHING
        self.old_state = State(0, 0, 0, 5, 0, False, 0, 3, 100, 0)

        self.model = get_model()

        self.tick = 0

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

    def die(self):
        self.model.update(self.old_state.as_tuple(), self.old_state.as_tuple(), self.old_action, -10)
        self.model.save()

    def win(self):
        self.model.update(self.old_state.as_tuple(), self.old_state.as_tuple(), self.old_action, 100)
        self.model.save()

    def reset(self, arena_description: ArenaDescription) -> None:
        self.tick = 0

        self.arena = Arena.load(arena_description.name)
        self.arena.menhir_position = arena_description.menhir_position

        # matrix = [[0] * self.arena.size[0]] * self.arena.size[1]
        # for coords, tile in self.arena.terrain.items():
        #     x, y = coords
        #     matrix[x][y] = MAP_TILES_COST.get(tile.description().type, 0)
        # grid = Grid(matrix=matrix)

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        self.tick += 1

        new_state = get_state(knowledge, self.arena, self.tick)

        reward = calculate_reward(self.old_state, new_state, self.old_action)

        # print(reward)

        self.model.update(self.old_state.as_tuple(), new_state.as_tuple(), self.old_action, reward)

        new_action = self.model.get_next_action(new_state)

        self.old_action = new_action
        self.old_state = new_state

        return new_action


POTENTIAL_CONTROLLERS = [
    BotElkaController("Z nami na pewno zdasz")
]
