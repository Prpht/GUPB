from gupb.model import arenas
from gupb.model import characters


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BotElka:
    def __init__(self, first_name: str):
        self.first_name: str = first_name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BotElka):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return characters.Action.ATTACK

    @property
    def name(self) -> str:
        return f'BotElka{self.first_name}'


POTENTIAL_CONTROLLERS = [
    BotElka("Elka")
]
