from gupb import controller
from gupb.model import characters, arenas, weapons
from gupb.model import coordinates as cord
from .mapa import Mapa
from .strategie import FirstStrategy
from .utils import CHAMPION_STARTING_HP
from typing import Optional


class MalyKonik(controller.Controller):

    def __init__(self, nick: str) -> None:
        self.nick: str = nick
        self.weapon_name: Optional[str] = None
        self.health: int = CHAMPION_STARTING_HP
        self.position: Optional[cord.Coords] = None
        self.orientation: characters.Facing = characters.Facing.random()
        self.map: Mapa = Mapa()
        self.strategy: FirstStrategy = FirstStrategy(self.map,
                                                     self.weapon_name,
                                                     self.position,
                                                     self.orientation)

    def __hash__(self) -> int:
        return hash(self.nick)

    def __eq__(self, other_object) -> bool:
        if isinstance(other_object, MalyKonik):
            return self.nick == other_object.nick
        return False

    def __update_myself(self, knowledge: characters.ChampionKnowledge = None) -> None:
        self.position = knowledge.position
        tile = knowledge.visible_tiles.get(self.position)
        character = tile.character if tile else None

        if character:
            self.health = character.health
            self.orientation = character.facing

            weapon_name = character.weapon.name

            match weapon_name:
                case 'knife':
                    self.weapon = weapons.Knife()
                    self.weapon_name = 'knife'
                case 'sword':
                    self.weapon = weapons.Sword()
                    self.weapon_name = 'sword'
                case 'bow_loaded':
                    self.weapon = weapons.Bow()
                    self.weapon.ready = True
                    self.weapon_name = 'bow_loaded'
                case 'bow_unloaded':
                    self.weapon = weapons.Bow()
                    self.weapon.ready = False
                    self.weapon_name = 'bow_unloaded'
                case 'axe':
                    self.weapon = weapons.Axe()
                    self.weapon_name = 'axe'
                case 'amulet':
                    self.weapon = weapons.Amulet()
                    self.weapon_name = 'amulet'
                case _:
                    raise ValueError(f'No Weapon named {weapon_name} found')

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.__update_myself(knowledge)

        self.map.read_information(knowledge)

        self.strategy.set_position_and_orientation(self.position, self.orientation)
        self.strategy.set_weapon(self.weapon_name)

        next_move = self.strategy.best_choice(knowledge)

        # self.map.reset_enemies()

        return next_move

        #  Z naładowanym łukiem można chodzić, więc jeżeli tylko go mamy to go ładujmy
        # if isinstance(self.weapon, weapons.Bow) and not self.weapon.ready:
        #     return characters.Action.ATTACK

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.map.reset_map(arena_description)
        self.strategy = FirstStrategy(self.map,
                                      self.weapon_name,
                                      self.position,
                                      self.orientation)

    @property
    def name(self) -> str:
        return self.nick

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN
