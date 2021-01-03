from gupb.controller import Controller
from gupb.model import characters, arenas
from gupb.model.characters import Action, ChampionKnowledge


class AIController(Controller):
    def __init__(self, uname):
        self.uname = uname
        self.knowledge = None
        self.menhir_position = None
        self.next_action = Action.DO_NOTHING

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET

    @property
    def name(self):
        return f"AiController_{self.uname}"

    def decide(self, knowledge: ChampionKnowledge):
        self.knowledge = knowledge
        return self.next_action

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_position = arena_description.menhir_position
