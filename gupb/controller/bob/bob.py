from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from .bob_utils import determine_facing_action
from collections import deque


class Bob(controller.Controller):
    def __init__(self, bot_name: str) -> None:
        self.bot_name = bot_name
        self.prev_pos = None
        self.previous_positions = deque(maxlen=16)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Bob):
            return self.bot_name == other.bot_name
        return False

    def __hash__(self) -> int:
        return hash(self.bot_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        pos = knowledge.position
        action = determine_facing_action(knowledge, self.previous_positions)
        self.previous_positions.appendleft(pos)
        return action

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return self.bot_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BOB

POTENTIAL_CONTROLLERS = [
    Bob("Bob"),
]