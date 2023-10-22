import abc
import enum
from collections import defaultdict
from typing import NamedTuple, Iterator
import networkx as nx

from gupb.model import characters, arenas, tiles
from gupb.model.coordinates import Coords

from .utils import manhattan_distance


class KnowledgeSource(abc.ABC):
    def __init__(self):
        self.epoch: int = 0

    @abc.abstractmethod
    def update(self, champion_knowledge: characters.ChampionKnowledge, epoch: int):
        pass

    @abc.abstractmethod
    def reset(self, arena_description: arenas.ArenaDescription):
        pass


class TerrainType(enum.StrEnum):
    LAND = 'land'
    SEA = 'sea'
    WALL = 'wall'
    MENHIR = 'menhir'


class MapKnowledge(KnowledgeSource):
    def __init__(self):
        super().__init__()
        self.width: int | None = None
        self.height: int | None = None
        self.menhir_pos: Coords | None = None
        self.tiles_info_as_last_seen: dict[Coords, tiles.TileDescription | None] = defaultdict(lambda: None)

        # todo: graph for pathing

    def update(self, champion_knowledge: characters.ChampionKnowledge, epoch: int):
        self.epoch = epoch
        for coords, tile_info in champion_knowledge.visible_tiles.items():
            self.tiles_info_as_last_seen[coords] = tile_info
            if tile_info.type == 'menhir' and not self.menhir_pos:
                self.menhir_pos = coords


    def reset(self, arena_description: arenas.ArenaDescription):
        super().__init__()
        self.tiles_info_as_last_seen = defaultdict(lambda: None)


    def terrain_at(self, pos: Coords) -> TerrainType | None:
        if tile_info := self.tiles_info_as_last_seen[pos] is None:
            return None
        return TerrainType(tile_info.type)


    def tile_info_at(self, pos: Coords) -> tiles.TileDescription | None:
        return self.tiles_info_as_last_seen[pos]



class PlayersKnowledge(KnowledgeSource):
    def __init__(self, own_name: str | None = None):
        super().__init__()
        self.n_players: int | None = None
        self.n_players_alive: int | None = None
        self._own_name: str | None = own_name

        self.players_time_last_seen: dict[str, int] = {self._own_name: 0}
        self.players_history: dict[str, dict[int, tuple[characters.ChampionDescription, Coords]]] = defaultdict(dict)

        self.own_player_history: dict[int, tuple[characters.ChampionDescription, Coords]] = \
            self.players_history[self._own_name]
        self.own_player_pos: Coords = Coords(0, 0)
        self.own_player_facing: characters.Facing = characters.Facing.UP

    def update(self, champion_knowledge: characters.ChampionKnowledge, epoch: int):
        self.epoch = epoch
        self.own_player_pos = champion_knowledge.position
        self.own_player_facing = champion_knowledge.visible_tiles[self.own_player_pos].character.facing
        self.n_players_alive = champion_knowledge.no_of_champions_alive
        for coords, tile_info in champion_knowledge.visible_tiles.items():
            if character_info := tile_info.character:
                char_key = character_info.controller_name
                self.players_time_last_seen[char_key] = self.epoch
                self.players_history[char_key][self.epoch] = character_info, coords

    def reset(self, arena_description: arenas.ArenaDescription):
        self.__init__()

    def get_own_champion_info(self) -> characters.ChampionDescription:
        return self.own_player_history[self.epoch][0]

    def iter_visible_players_info(self) -> Iterator[characters.ChampionDescription]:
        for player_hist in self.players_history.values():
            try:
                yield player_hist[self.epoch]
            except KeyError:
                continue

    def iter_visible_players_info_by_distance(self) -> Iterator[characters.ChampionDescription]:
        yield from sorted(
            self.iter_visible_players_info(),
            key=lambda oth: manhattan_distance(self.own_player_history[self.epoch][1],
                                               self.players_history[oth.controller_name][self.epoch][1])
        )


class KnowledgeSources(KnowledgeSource):
    def __init__(self):
        super().__init__()
        self.epoch: int = 0
        self.map: MapKnowledge = MapKnowledge()
        self.players: PlayersKnowledge = PlayersKnowledge()

        # todo: temporary
        self.oridinary_chaos_str = """
        ========================
        =####.##=....====....===
        ==#A...#==....====..=..=
        ==.S....==....==.......=
        ==#....#===......=.....=
        =##....#====..#..#.#...=
        =####.##====......M#=..=
        ==.....=====.....#.....=
        ==.###.####==..#.#.#...=
        ===#.#.####==....#.#...=
        =....#...##.......===..=
        =###..B.....=...====.=.=
        =#...##.##..===...==...=
        =#...#==.#.===........#=
        =#..S#=.....==.........=
        =#...#==...===##.###...=
        =#.###=..#..==#....#==.=
        =....=.......=#BA...====
        ==..==...##........#====
        ==.....#.###..##.###====
        =====..####....M..======
        =.....####....##.#======
        =.====##....=.....======
        ========================
        """.strip()
        self.chaos_graph: nx.Graph = self._get_graph_from_map()

    def _get_graph_from_map(self) -> nx.Graph:
        self.chaos_graph = nx.Graph()
        for y, line in enumerate(self.oridinary_chaos_str.split('\n')):
            for x, char in enumerate(line.strip()):
                if char != '=' and char != '#':
                    self.chaos_graph.add_node((x, y))
                    for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                        neighbor = (x + dx, y + dy)
                        if neighbor in self.chaos_graph.nodes:
                            self.chaos_graph.add_edge((x, y), neighbor)
        return self.chaos_graph


    def find_next_move_on_path(self, start: tuple, end: tuple) -> tuple | None:
        try:
            path = nx.shortest_path(self.chaos_graph, source=start, target=end)
            return path[1] if len(path) > 1 else None
        except nx.NetworkXNoPath:
            return None


    def update(self, champion_knowledge: characters.ChampionKnowledge, epoch: int):
        for ks in self:
            ks.update(champion_knowledge, epoch)


    def reset(self, arena_description: arenas.ArenaDescription):
        for ks in self:
            ks.reset(arena_description)


    # todo: def praise(self, score: int)


    def __iter__(self) -> Iterator[KnowledgeSource]:
        yield from (self.map, self.players)

    def get_tile_in_direction(self, facing: characters.Facing) -> tiles.TileDescription:
        return self.map.tile_info_at(self.players.own_player_pos + facing.value)

    def get_tile_info_in_front_of(self) -> tiles.TileDescription:
        return self.get_tile_in_direction(self.players.own_player_facing)
