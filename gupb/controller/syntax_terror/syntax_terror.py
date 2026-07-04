import pickle
from pathlib import Path

from gupb.controller import Controller
from gupb.model import arenas, characters

from .brain import Brain
from .memory import MapMemory
from .mist import filter_knowledge
from .policy_nn import FeedForwardNetwork

_MODEL_PATH = Path(__file__).resolve().parent / "model.pkl"


def _load_network() -> FeedForwardNetwork:
    with _MODEL_PATH.open("rb") as f:
        net = pickle.load(f)
    if isinstance(net, dict) and "initial_game_state" in net:
        game = net["initial_game_state"]
        for champion in game.champions:
            if isinstance(champion.controller, SyntaxTerror):
                net = champion.controller.brain.model.net
                break
    if not isinstance(net, FeedForwardNetwork):
        raise TypeError(f"Expected FeedForwardNetwork in {_MODEL_PATH}")
    return net


class SyntaxTerror(Controller):
    def __init__(self, first_name: str):
        self.first_name = first_name
        self.memory = MapMemory()
        self.brain = Brain(_load_network())

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SyntaxTerror) and self.first_name == other.first_name

    def __hash__(self) -> int:
        return hash(self.first_name)

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PINK

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.memory = MapMemory()
        self.brain.reset()

    def praise(self, score: int) -> None:
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        knowledge = filter_knowledge(knowledge)
        self.memory.observe(knowledge)
        action = self.brain.pick_action(knowledge, self.memory)
        if self.memory.my_weapon == "scroll" and action == characters.Action.ATTACK:
            self.memory.my_scroll_charges = max(
                0, self.memory.my_scroll_charges - 1
            )
        return action
