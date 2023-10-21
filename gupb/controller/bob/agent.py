from .. import Controller

import random

from typing import Protocol, Dict
from gupb.model.characters import ChampionKnowledge, Action, Tabard, ChampionDescription
from gupb.model import weapons
from gupb.model.arenas import ArenaDescription
from gupb.model.coordinates import Coords
from gupb.model.tiles import TileDescription

POSSIBLE_RANDOM_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]

# This can be later switched to MAB :)
# Higher == better
WEAPONS_TIER_LIST = [
    weapons.Knife,
    weapons.Bow,
    weapons.Sword,
    weapons.Axe,
    weapons.Amulet
]


class Strategy(Protocol):
    def perform(self, curren_pos: Coords) -> Action:
        pass


class GoToStrategy(Strategy):
    def __init__(self, target: Coords):
        pass


class RandomStrategy(Strategy):
    def __init__(self):
        pass

    def perform(self, curren_pos: Coords) -> Action:
        return random.choice(POSSIBLE_RANDOM_ACTIONS)


class FSMBot(Controller):
    def __init__(self):
        self.current_strategy = RandomStrategy()
        self.champ_data: ChampionDescription = None

    def __eq__(self, other) -> bool:
        return isinstance(other, FSMBot)

    def __hash__(self) -> int:
        return -1

    def reset(self, arena_description: ArenaDescription) -> None:
        pass

    def analyse_field(self, pos, visibility: Dict[Coords, TileDescription]):
        res = {
            'weapons': [],
            'enemies': [],
            'menhir': [],
            'effects': []
        }

        for coord, tile in visibility.items():
            if coord == pos:
                continue
            if tile.loot is not None:
                res['weapons'].append((coord, tile.loot))
            if tile.character is not None:
                res['enemies'].append((coord, tile.character))
            if tile.type == 'menhir':
                res['menhir'].append(coord)
            if tile.effects is not None:
                res['effects'].append((coord, tile.effects))
        return res

    # def can_attack_someone(self, enemies_loc, tiles) -> bool:
    #     weapons_range = self.champ_data.weapon.cut_positions()

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        champ_pos = knowledge.position
        self.champ_data = knowledge.visible_tiles[champ_pos].character
        points_of_interest = self.analyse_field(champ_pos, knowledge.visible_tiles)

        return self.current_strategy.perform(champ_pos)

    def praise(self, score: int) -> None:
        pass

    @property
    def name(self) -> str:
        return 'Bob'

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.GREEN
