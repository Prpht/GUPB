import numpy as np

from gupb.controller import Controller
from gupb.controller.forrest_gump.strategies import *
from gupb.controller.forrest_gump.utils import CharacterInfo
from gupb.model import arenas, characters, coordinates


class ForrestGumpController(Controller):
    def __init__(self, first_name: str) -> None:
        self.first_name = first_name

        self.strategies = []
        self.current_strategy = None
        self.default_strategy = None

        self.last_score = 0
        self.menhir = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ForrestGumpController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        character_info = CharacterInfo(
            position=knowledge.position,
            facing=knowledge.visible_tiles[knowledge.position].character.facing,
            weapon=knowledge.visible_tiles[knowledge.position].character.weapon.name,
            health=knowledge.visible_tiles[knowledge.position].character.health,
            menhir=self.menhir
        )

        ordered_tiles = np.array([tile for tile in knowledge.visible_tiles])
        pos_ndarray = np.array([knowledge.position.x, knowledge.position.y])
        order = np.argsort(np.abs(ordered_tiles - pos_ndarray).sum(axis=1))
        ordered_tiles = ordered_tiles[order]

        if self.current_strategy.should_leave(character_info):
            next_strategy = self.default_strategy
        else:
            next_strategy = self.current_strategy

        for x, y in ordered_tiles:
            coords = coordinates.Coords(x, y)
            tile = knowledge.visible_tiles[coords]

            if coords == knowledge.position:
                continue

            if tile.type == 'menhir':
                self.menhir = coords

            for strategy in self.strategies:
                if strategy.should_enter(coords, tile, character_info) and strategy.priority > next_strategy.priority:
                    next_strategy = strategy

        if next_strategy != self.current_strategy:
            self.current_strategy.left()
            self.current_strategy = next_strategy
            self.current_strategy.enter()

        return self.current_strategy.next_action(character_info)

    def praise(self, score: int) -> None:
        self.last_score = score

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.strategies = [
            Explore(arena_description, max_age=20),
            GrabPotion(arena_description, max_distance=5),
            GrabWeapon(arena_description, max_distance=5),
            MinMax(arena_description, enter_distance=5, max_depth=3),
            Run(arena_description, close_distance=5, far_distance=10, distance_to_menhir=7)
        ]

        self.default_strategy = self.strategies[0]
        self.current_strategy = self.default_strategy
        self.current_strategy.enter()

        self.menhir = None

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ORANGE
