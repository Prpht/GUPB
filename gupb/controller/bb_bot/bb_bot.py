from gupb.controller.bb_bot.commands import IdentifyFacingCommand
from gupb.controller.bb_bot.helpers import should_attack
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BBBotController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.scanedArena = {}
        self.currentPos = coordinates.Coords(0, 0)
        self.facing = characters.Facing.UP  # temporary facing
        self.currentCommand = IdentifyFacingCommand(self)
        self.iteration = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BBBotController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.__init__(self.first_name)
        self.menhirPos = arena_description.menhir_position

        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.iteration += 1
        self.currentPos = knowledge.position
        self.scanedArena.update(knowledge.visible_tiles)
        if should_attack(knowledge):
            return characters.Action.ATTACK
        action = self.currentCommand.decide(knowledge)
        if (action == characters.Action.TURN_LEFT):
            self.facing = self.facing.turn_left()
        elif (action == characters.Action.TURN_RIGHT):
            self.facing = self.facing.turn_right()
        return action

    @property
    def name(self) -> str:
        return f'BBBotController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE
