from gupb.controller.bb_bot.commands import IdentifyFacingCommand
from gupb.controller.bb_bot.learning_controller import LearningController
from gupb.controller.bb_bot.model import Model

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import weapons
from gupb.model import tiles

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

class Weapon:
    Knife = weapons.Knife()
    Sword = weapons.Sword()
    Bow = weapons.Bow()
    Axe = weapons.Axe()
    Amulet = weapons.Amulet()

    nameToWeapon = {
        "knife":Knife,
        "sword":Sword,
        "bow":Bow,
        "axe":Axe,
        "amulet":Amulet
    }

    @staticmethod
    def weaponFromName(name:str):
        return Weapon.nameToWeapon.get(name)


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BBBotController:
    nameToTile = {
        "land":tiles.Land(),
        "sea":tiles.Sea(),
        "wall":tiles.Wall(),
        "menhir":tiles.Menhir()
    }

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.scanedArena = {}
        self.currentPos = coordinates.Coords(0, 0)
        self.facing = characters.Facing.UP  # temporary facing
        self.facingIsCorrect = False
        self.currentCommand = IdentifyFacingCommand(self)
        self.iteration = 0
        self.learning = False
        self.heldWeapon = Weapon.Knife

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BBBotController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.__init__(self.first_name)
        self.menhirPos = arena_description.menhir_position
        self.arena = arenas.Arena.load(arena_description.name)
        # W, H = self.arena.size
        # self.learning_model = Model.new_model('sarsa', W, H)
        self.learning_model = Model.from_config('sarsa')
        self.learning_controller = LearningController(self.learning_model, self)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.iteration += 1
        self.currentPos = knowledge.position
        self.scanedArena.update(knowledge.visible_tiles)
        
        #decide base on current policy
        action = self.currentCommand.decide(knowledge)

        if self.learning:
            if self.iteration > 1:
                state, action = self.learning_controller.episode(1, knowledge)
            else:
                state, action = self.learning_controller.initial_ep(knowledge)

            return POSSIBLE_ACTIONS[action]

        #atack if possible
        if self.facingIsCorrect and self.should_attack(knowledge):
            return characters.Action.ATTACK

        #update facing
        if (action == characters.Action.TURN_LEFT):
            self.facing = self.facing.turn_left()
        elif (action == characters.Action.TURN_RIGHT):
            self.facing = self.facing.turn_right()

        #update held weapon        
        if (self.facingIsCorrect and action == characters.Action.STEP_FORWARD):
            tileInFront = self.scanedArena[coordinates.add_coords(self.currentPos, self.facing.value)]
            if(tileInFront.loot is not None):
                self.heldWeapon = Weapon.weaponFromName(tileInFront.loot.name)
                pass

        return action

    def die(self):
        self.learning_model.config["rewards"].append(self.learning_controller.rewards)
        self.learning_model.config["epoch"] += 1
        self.learning_model.snapshot()

    def createTerrain(self):
        terrain = {}
        for k, v in self.scanedArena.items():
            terrain[k] = self.nameToTile[v.type]
        return terrain

    def should_attack(self, knowledge):
        result = False
        for pos in self.heldWeapon.cut_positions(self.createTerrain(), knowledge.position, self.facing):
            result |= (self.scanedArena[pos].character is not None and self.scanedArena[pos].character.controller_name != self.name)
        return result

    @property
    def name(self) -> str:
        return f'BBBotController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE
