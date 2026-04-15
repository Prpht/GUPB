from gupb import controller
from gupb.model import arenas
from gupb.model import characters


class CzakNoris(controller.Controller):
    def __init__(self, bot_name: str) -> None:
        self.bot_name = bot_name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CzakNoris):
            return self.bot_name == other.bot_name
        return False

    def __hash__(self) -> int:
        return hash(self.bot_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return characters.Action.TURN_LEFT

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return self.bot_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.CZAK_NORIS
