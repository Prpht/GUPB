import abc
import enum
from collections import defaultdict
from typing import NamedTuple, Iterator
import networkx as nx

from gupb.model import characters, arenas, tiles
from gupb.model.coordinates import Coords, add_coords

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
        self.map_start: Coords | None = None
        self.map_end: Coords | None = None
        self.map_center: Coords = Coords(11, 13)
        self.menhir_pos: Coords | None = None
        self.epoch: int = 0
        # ! __subclasses__ works only for direct children
        self.impassable_tiles: list[str] = [tile.__class__.__name__.lower() for tile in tiles.Tile.__subclasses__() if not tile.terrain_passable()]
        self.graph: nx.Graph = nx.Graph()

        # todo: implement mist sensing and menhir position approx based on mist

    def update(self, champion_knowledge: characters.ChampionKnowledge, epoch: int):
        self.epoch = epoch
        for coords, tile_info in champion_knowledge.visible_tiles.items():
            # update map graph
            if self.graph.has_node(coords):
                nx.set_node_attributes(self.graph, {coords: tile_info._asdict(), "tile_info": tile_info})
            else:
                # extract tile info directly to map graph as node attributes
                # might be useful for fast key location finding
                self.graph.add_node(coords, **tile_info._asdict(), tile_info=tile_info)
                # self.graph.nodes[coords]['tile_info'] = tile_info
                # add edges if tile is passable
                if tile_info.type not in self.impassable_tiles:
                    self._update_paths(coords)
            # update menhir position
            if tile_info.type == 'menhir' and not self.menhir_pos:
                self.menhir_pos = coords
        if self.epoch % 10 == 0:
            # update presumed map size
            self._update_map_center()


    def reset(self, arena_description: arenas.ArenaDescription):
        super().__init__()
        self.graph = nx.Graph()

    
    def _update_paths(self, coords: Coords):
        """Add edges if terrain is passable."""
        x, y = coords
        neighbors = [Coords(x-1, y), Coords(x+1, y), Coords(x, y-1), Coords(x, y+1)]
        for neighbor in neighbors:
            if neighbor in self.graph.nodes() and self.graph.nodes[neighbor]["type"] not in self.impassable_tiles:
                self.graph.add_edge(coords, neighbor)
    
    def _update_map_center(self):
        nodes = list(self.graph.nodes)
        center = nodes[0]
        for node in nodes[1:]:
            center = add_coords(center, node)
        # uncomment if mul_coords allows float as other
        # self.map_center = mul_coords(add_coords(self.map_start, self.map_end), 1/len(self.graph.nodes))
        self.map_center = Coords(*[int(el / len(self.graph.nodes)) for el in center])


    def terrain_at(self, pos: Coords) -> TerrainType | None:
        return TerrainType(self.graph.nodes[pos]["type"]) if pos in self.graph.nodes else None


    def tile_info_at(self, pos: Coords) -> tiles.TileDescription | None:
        return self.graph.nodes[pos]["tile_info"] if pos in self.graph.nodes else None


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
        self.own_player_history = self.players_history[self._own_name]
        self.n_players_alive = champion_knowledge.no_of_champions_alive
        for coords, tile_info in champion_knowledge.visible_tiles.items():
            if character_info := tile_info.character:
                char_key = character_info.controller_name
                self.players_time_last_seen[char_key] = self.epoch
                self.players_history[char_key][self.epoch] = character_info, coords

    def reset(self, arena_description: arenas.ArenaDescription):
        self.__init__(self._own_name)

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
    def __init__(self, own_name):
        super().__init__()
        self.epoch: int = 0
        self.map: MapKnowledge = MapKnowledge()
        self.players: PlayersKnowledge = PlayersKnowledge(own_name)
        # todo: make this work
        # self.meta_ratings: Dict[MetaStrategy, int] = {meta: 0 for meta in MetaStrategy.__subclasses__}


    def find_next_move_on_path(self, start: Coords, end: Coords) -> Coords | None:
        # returns None if destination is reached
        try:
            path = nx.shortest_path(self.map.graph, source=start, target=end)
            return path[1] if len(path) > 1 else None
        except nx.NetworkXNoPath:
            # happens when end is impassable
            pass
        # find next best tile to go to
        distances = sorted(
            [
                (manhattan_distance(coord, end), coord)
                for coord in self.map.graph.nodes()
                if self.map.graph.nodes[coord]['type'] not in self.map.impassable_tiles
            ],
            key=lambda x: x[0]
        )
        best_match = distances[0][1]
        try:
            path = nx.shortest_path(self.map.graph, source=start, target=best_match)
            return path[1] if len(path) > 1 else None
        except nx.NetworkXNoPath:
            return None


    def update(self, champion_knowledge: characters.ChampionKnowledge, epoch: int):
        for ks in self:
            ks.update(champion_knowledge, epoch)


    def reset(self, arena_description: arenas.ArenaDescription):
        for ks in self:
            ks.reset(arena_description)

    def praise(self, score: int, meta_strat):
        # todo: make this work
        # self.meta_ratings[meta] += score
        ...


    def __iter__(self) -> Iterator[KnowledgeSource]:
        yield from (self.map, self.players)

    def get_tile_in_direction(self, facing: characters.Facing) -> tiles.TileDescription:
        return self.map.tile_info_at(self.players.own_player_pos + facing.value)

    def get_tile_info_in_front_of(self) -> tiles.TileDescription:
        return self.get_tile_in_direction(self.players.own_player_facing)
