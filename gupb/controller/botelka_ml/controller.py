from pathfinding.core.grid import Grid

from gupb.controller.botelka_ml.brain import init_q, save_q
from gupb.controller.botelka_ml.model import get_model
from gupb.controller.botelka_ml.rewards import calculate_reward
from gupb.controller.botelka_ml.wisdom import Wisdom
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
        self.old_state = [0]*16

        self.wisdom = None

        self.episode = 0
        self.game_no = 0

        self.model = get_model()

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
        self.model.update(self.old_state, self.old_state, self.old_action, -10)
        if self.game_no > 298:
            self.model.save()
            print("saved")

    def win(self):
        # TODO: self.old_state == self.old_state (???)
        self.model.update(self.old_state, self.old_state, self.old_action, 100)
        # if self.game_no > 298:
        self.model.save()
        print("saved (win)")

    def reset(self, arena_description: ArenaDescription) -> None:
        self.game_no += 1
        self.arena = Arena.load(arena_description.name)
        self.arena.menhir_position = arena_description.menhir_position

        matrix = [[0] * self.arena.size[0]] * self.arena.size[1]
        for coords, tile in self.arena.terrain.items():
            x, y = coords
            matrix[x][y] = MAP_TILES_COST.get(tile.description().type, 0)
        grid = Grid(matrix=matrix)

        self.wisdom = Wisdom(self.arena, None, self.name, grid)
        save_q(self.q)

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        self.episode += 1

        self.wisdom.next_knowledge(knowledge)
        wisdom = self.wisdom

        bot_facing =  wisdom.bot_facing.value

        new_state = wisdom.relative_enemies_positions + [wisdom.mist_visible, bot_facing[0], bot_facing[1], 
        wisdom.reach_menhir_before_mist] + wisdom.relative_menhir_position
        reward = calculate_reward(wisdom)

        self.model.update(self.old_state, new_state, self.old_action, reward)  # Let the agent update internals

        new_action = self.model.get_next_action(new_state)

        self.old_action = new_action
        self.old_state = new_state

        return new_action


POTENTIAL_CONTROLLERS = [
    BotElkaController("Z nami na pewno zdasz")
]
