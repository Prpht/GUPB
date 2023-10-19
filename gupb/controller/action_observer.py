from gupb import controller
from gupb.environment.observer import Observer, Observable
from gupb.model import arenas
from gupb.model.characters import Action, ChampionKnowledge, Tabard


class RlAgentController(
    controller.Controller, Observer[Action], Observable[ChampionKnowledge]
):
    def __init__(self) -> None:
        # TODO
        super().__init__()

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        self.observable_state = knowledge
        action = self.wait_for_observed()
        return action

    def praise(self, score: int) -> None:
        return super().praise(score)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        return super().reset(arena_description)

    @property
    def name(self) -> str:
        # TODO
        return super().name

    @property
    def preferred_tabard(self) -> Tabard:
        # TODO
        return super().preferred_tabard
