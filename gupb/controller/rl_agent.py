from gupb import controller
from gupb.model import arenas
from gupb.model import characters


class RlAgentController(controller.Controller):
    def __init__(self) -> None:
        # TODO
        super().__init__()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return super().decide(knowledge)

    def praise(self, score: int) -> None:
        return super().praise(score)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        return super().reset(arena_description)

    @property
    def name(self) -> str:
        # TODO
        return super().name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        # TODO
        return super().preferred_tabard

    @property
    def knowledge(self) -> characters.ChampionKnowledge:
        # TODO last knowledge or sth
        pass
