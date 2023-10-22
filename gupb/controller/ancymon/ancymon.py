import random

from gupb import controller
from gupb.model import arenas, characters
from gupb.model.weapons import Knife
from gupb.model import tiles
from gupb.model import coordinates

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

# PRIORITY_LIST = {1: "consumable", 2: "character", 3: "loot", 4: "type"}


class AncymonController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.discovered_map = dict()
        self.champion = None
        self.position = None
        self.menhir = None
        self.weapon = Knife
        # self.priority_neighbors = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AncymonController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.position = knowledge.position
        self.champion = knowledge.visible_tiles[knowledge.position].character
        self.update_discovered_map(knowledge.visible_tiles)

        # self.priority_neighbors = self.check_surrounding()
        # # if not self.priority_neighbors:
        new_position = self.position + self.champion.facing.value
        if self.collect_loot(new_position):
            return POSSIBLE_ACTIONS[2]
        elif self.should_attack(new_position):
            return POSSIBLE_ACTIONS[3]
        elif self.can_move_forward():
            return random.choices(
                population=POSSIBLE_ACTIONS[:3], weights=(20, 20, 60), k=1
            )[0]
        else:
            return random.choice([POSSIBLE_ACTIONS[0], POSSIBLE_ACTIONS[1]])

    def update_discovered_map(self, visible_tiles):
        for coords, description in visible_tiles.items():
            self.discovered_map[coords] = description
            if self.discovered_map[coords].type == "menhir":
                self.menhir = coords

    def can_move_forward(self):
        new_position = self.position + self.champion.facing.value

        if self.is_mist(new_position):
            return False
        return (
            self.discovered_map[new_position].type == "land"
            and not self.discovered_map[new_position].character
        )

    def should_attack(self, new_position):
        if self.discovered_map[new_position].character:
            if (
                self.discovered_map[new_position].character.health
                <= self.discovered_map[self.position].character.health
            ):
                return True
            # opponent is not facing us
            elif (
                new_position + self.discovered_map[new_position].character.facing.value
                == self.position
            ):
                return False

        return False

    def collect_loot(self, new_position):
        return (
            self.discovered_map[new_position].loot and self.weapon == Knife
        ) or self.discovered_map[new_position].consumable

    # freezes when stuck in mist
    def is_mist(self, new_position):
        tile = self.discovered_map[new_position].effects
        if tile:
            effect = tile[0].type
            if effect == "mist":
                return True
        return False

    # def check_surrounding(self):
    #     tile = self.position

    #     neighbourhood = [
    #         coordinates.Coords(tile.x, tile.y + 1),
    #         coordinates.Coords(tile.x + 1, tile.y + 1),
    #         coordinates.Coords(tile.x + 1, tile.y),
    #         coordinates.Coords(tile.x + 1, tile.y - 1),
    #         coordinates.Coords(tile.x, tile.y - 1),
    #         coordinates.Coords(tile.x - 1, tile.y - 1),
    #         coordinates.Coords(tile.x - 1, tile.y),
    #         coordinates.Coords(tile.x - 1, tile.y - 1),
    #     ]
    #     neighbours = {}

    #     for neighbour in neighbourhood:
    #         new_position = tile + neighbour
    #         if new_position in self.discovered_map:
    #             tile_description = self.discovered_map[new_position]
    #             neighbours[neighbour] = tile_description

    #     sorted_neighbours = sorted(neighbours.items(), key=lambda x: x[1], reverse=True)

    #     if sorted_neighbours:
    #         return sorted_neighbours[0]
    #     return None

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return f"{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ANCYMON

    # TODO
    # def chaise_enemy()
    # def avoid_mist()
    # def go_to_menhir
