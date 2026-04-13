from gupb import controller
from gupb.model import arenas, characters

class BiwakSpot(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name = first_name
    
    def __hash__(self):
        return hash(self.first_name)
    
    def __eq__(self, value):
        if isinstance(value, BiwakSpot):
            return self.first_name == value.first_name
        return False

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        raise NotImplementedError

    def praise(self, score: int) -> None:
        raise NotImplementedError

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        raise NotImplementedError

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BLUE