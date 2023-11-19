from .. import Controller

import random

from typing import Protocol, Dict
from gupb.model.characters import ChampionKnowledge, Action, Tabard, ChampionDescription
from gupb.model import weapons, tiles
from gupb.model.arenas import ArenaDescription
from gupb.model.coordinates import Coords
from gupb.model.tiles import TileDescription

# Random comment as we did not change anything
# Once again

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

WEAPONS_MAPPING = {
    'axe': weapons.Axe,
    'bow': weapons.Bow,
    'sword': weapons.Sword,
    'amulet': weapons.Amulet,
    'knife': weapons.Knife
}

TERRAIN_MAPPING = {
    'land': tiles.Land,
    'sea': tiles.Sea,
    'wall': tiles.Wall,
    'menhir': tiles.Menhir
}


class Strategy(Protocol):
    def perform(self, champion: ChampionDescription, knowledge: ChampionKnowledge) -> Action:
        pass


class RandomStrategy(Strategy):
    def __init__(self):
        pass

    def perform(self, champion: ChampionDescription, knowledge: ChampionKnowledge) -> Action:
        options = [Action.TURN_RIGHT]
        forward_pos = champion.facing.value + knowledge.position
        if TERRAIN_MAPPING[knowledge.visible_tiles[forward_pos].type].passable:
            options.extend([Action.STEP_FORWARD] * 2 + [Action.TURN_RIGHT])
        return random.choice(options)


class FSMBot(Controller):
    def __init__(self):
        self.current_strategy = RandomStrategy()
        self.champ_data: ChampionDescription = None

    def __eq__(self, other) -> bool:
        return isinstance(other, FSMBot)

    def __hash__(self) -> int:
        return -1

    def reset(self, game_no: int, arena_description: ArenaDescription) -> None:
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
            if len(tile.effects) > 0:
                res['effects'].append((coord, tile.effects))
        return res

    def should_attack(self, knowledge: ChampionKnowledge) -> bool:
        weapon_obj = WEAPONS_MAPPING[self.champ_data.weapon.name]
        tiles_map = {
            pos: TERRAIN_MAPPING[tile.type]
            for pos, tile in knowledge.visible_tiles.items()
        }
        attacked_tiles = weapon_obj.cut_positions(tiles_map, knowledge.position, self.champ_data.facing)
        for tile in attacked_tiles:
            if tile in knowledge.visible_tiles and knowledge.visible_tiles[tile].character is not None:
                return True
        return False

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        champ_pos = knowledge.position
        self.champ_data = knowledge.visible_tiles[champ_pos].character

        if self.should_attack(knowledge):
            return Action.ATTACK

        return self.current_strategy.perform(self.champ_data, knowledge)

    def praise(self, score: int) -> None:
        pass

    @property
    def name(self) -> str:
        return 'Bob'

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.GREEN
