from gupb import controller
from gupb.controller.neat.model_config import NeatConfig
from gupb.model import arenas
from gupb.model import characters

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

NEAT_CONFIG = NeatConfig(
    network_name=None, # ENTER NETWORK NAME
    config_name="default_config"
)


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class KimDzongNeatJuniorController(controller.Controller):
    def __init__(self, first_name: str = "Kim Dzong Neat v_1", net=NEAT_CONFIG.network):
        self.first_name: str = first_name
        self.net = net

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KimDzongNeatJuniorController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        inputs = self.get_from_knowledge()
        output = self.net.activate(inputs)
        best_output_value = max(output)
        best_index = output.index(best_output_value)

        return POSSIBLE_ACTIONS[best_index]

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KIMDZONGNEAT

    def get_from_knowledge(self):
        return [0, 1]  # TO IMPL
