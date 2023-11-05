from gupb import controller
from .game_service import GameService
from gupb.model import characters, arenas


class FrogController(controller.Controller):
    def __init__(self, agent_name) -> None:
        self.game_service = None
        self.agent_name: str = agent_name

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.game_service = GameService(arena_description)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.game_service.get_action(knowledge)

    @property
    def name(self) -> str:
        return self.agent_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.FROG
