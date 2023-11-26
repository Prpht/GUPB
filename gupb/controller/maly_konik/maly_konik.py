import random
import traceback

from gupb import controller
from gupb.model import characters, arenas, weapons
from gupb.model import coordinates as cord
from .mapa import Mapa
from .strategie import FirstStrategy
from .utils import CHAMPION_STARTING_HP, ACTIONS
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
                                                     self.orientation,
                                                     self.health)

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
        self.map.read_information(knowledge, self.weapon_name)

        self.strategy.set_position_and_orientation(self.position, self.orientation)
        self.strategy.set_weapon(self.weapon_name)

        try:
            self.strategy.check_my_status(knowledge)

            if not self.strategy.future_moves:
                self.strategy.plan_my_moves()

            next_move = self.strategy.move(knowledge)
        except Exception as e:
            # traceback.print_exc()
            # print(e)
            # print(self.position)
            # print(self.strategy.future_moves)
            next_move = random.choices(ACTIONS, weights=(0, 1, 1, 4, 0, 2))[0]
            self.strategy.reset_moves()

        self.map.reset_enemies()

        return next_move

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.map.reset_map(arena_description)

        self.strategy = FirstStrategy(self.map,
                                      self.weapon_name,
                                      self.position,
                                      self.orientation,
                                      CHAMPION_STARTING_HP)
        #self.strategy.future_moves = []

    @property
    def name(self) -> str:
        return self.nick

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN
