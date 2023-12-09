import abc
import enum
from collections import defaultdict
from typing import NamedTuple, Iterator
import networkx as nx
import numpy as np
import scipy

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
        self.impassable_tiles: list[str] = ['sea', 'wall']
        self.graph: nx.Graph = nx.Graph()


    def update(self, champion_knowledge: characters.ChampionKnowledge, epoch: int):
        self.epoch = epoch
        for _coords, tile_info in champion_knowledge.visible_tiles.items():
            # update map graph
            coords = Coords(*_coords)  # fix because sometimes menhir_pos was a tuple (?)
            if self.graph.has_node(coords):
                # nx.set_node_attributes(self.graph, {coords: tile_info._asdict(), "tile_info": tile_info}) - chyba bug?
                nx.set_node_attributes(self.graph, {coords: {**tile_info._asdict(), "tile_info": tile_info}})
            else:
                # extract tile info directly to map graph as node attributes
                # might be useful for fast key location finding
                self.graph.add_node(coords, **tile_info._asdict(), tile_info=tile_info)

            # update menhir position
            if tile_info.type == 'menhir' and not self.menhir_pos:
                self.menhir_pos = coords

        # add edges if tile is passable (2nd pass to update all nodes first)
        for coords, tile_info in champion_knowledge.visible_tiles.items():
            if tile_info.type not in self.impassable_tiles:
                self._update_edges(coords)

        if self.epoch % 10 == 0:
            # update presumed map size
            self._update_map_center()
        if not any([data.get('type') == 'menhir' for _, data in self.graph.nodes(data=True)]):
            self.menhir_pos = self.get_approx_menhir_pos()


    def reset(self, arena_description: arenas.ArenaDescription):
        self.__init__()

    
    def _update_edges(self, coords: Coords):
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


    def iter_mist_coords(self) -> Iterator[Coords]:  # todo: use this
        for coord, node_attrs in self.graph.nodes.items():
            if any(eff.type == 'mist' for eff in node_attrs['effects']):
                yield coord


    def terrain_at(self, pos: Coords) -> TerrainType | None:
        return TerrainType(self.graph.nodes[pos]["type"]) if pos in self.graph.nodes else None


    def tile_info_at(self, pos: Coords) -> tiles.TileDescription | None:
        return self.graph.nodes[pos]["tile_info"] if pos in self.graph.nodes else None


    def get_approx_menhir_pos(self) -> Coords | None:  # todo: use this
        mist_coords = list(self.iter_mist_coords())
        if len(mist_coords) < 2:
            return None  # todo: if len(mist_coords) == 1 we can still run in the opposite direction
        mist_x = np.asarray([coord[0] for coord in self.iter_mist_coords()])
        mist_y = np.asarray([coord[1] for coord in self.iter_mist_coords()])

        # https://scipy-cookbook.readthedocs.io/items/Least_Squares_Circle.html

        def calc_R(xc, yc):
            """ calculate the distance of each 2D points from the center (xc, yc) """
            return np.sqrt((mist_x - xc) ** 2 + (mist_y - yc) ** 2)

        def f_2(c):
            """ calculate the algebraic distance between the data points and the mean circle centered at c=(xc, yc) """
            Ri = calc_R(*c)
            return Ri - Ri.mean()

        center_estimate = np.mean(mist_x), np.mean(mist_y)
        center_2, ier = scipy.optimize.leastsq(f_2, center_estimate)

        xc_2, yc_2 = center_2

        return Coords(round(xc_2), round(yc_2))


class PlayersKnowledge(KnowledgeSource):
    def __init__(self, own_name: str | None = None):
        super().__init__()
        self.n_players: int | None = None
        self.n_players_alive: int | None = None
        self.own_name: str | None = own_name

        self.players_time_last_seen: dict[str, int] = {self.own_name: 0}
        self.players_history: dict[str, dict[int, tuple[characters.ChampionDescription, Coords]]] = defaultdict(dict)

        self.own_player_history: dict[int, tuple[characters.ChampionDescription, Coords]] = \
            self.players_history[self.own_name]
        self.own_player_pos: Coords = Coords(0, 0)
        self.own_player_facing: characters.Facing = characters.Facing.UP


    @property
    def own_player_hp(self) -> int:
        return self.own_player_history[self.epoch][0].health


    @property
    def own_player_weapon(self) -> str:
        return self.own_player_history[self.epoch][0].weapon.name


    @property
    def own_player_prev_pos(self) -> Coords:
        return self.own_player_history[self.epoch - 1][1]


    def update(self, champion_knowledge: characters.ChampionKnowledge, epoch: int):
        self.epoch = epoch
        self.own_player_pos = champion_knowledge.position
        self.own_player_facing = champion_knowledge.visible_tiles[self.own_player_pos].character.facing
        self.own_player_history = self.players_history[self.own_name]
        self.n_players_alive = champion_knowledge.no_of_champions_alive
        for coords, tile_info in champion_knowledge.visible_tiles.items():
            if character_info := tile_info.character:
                char_key = character_info.controller_name
                self.players_time_last_seen[char_key] = self.epoch
                self.players_history[char_key][self.epoch] = character_info, coords

    def reset(self, arena_description: arenas.ArenaDescription):
        self.__init__(self.own_name)

    def get_own_champion_info(self) -> characters.ChampionDescription:
        return self.own_player_history[self.epoch][0]

    def iter_visible_players_info(self) -> Iterator[tuple[characters.ChampionDescription, Coords]]:
        for player_hist in self.players_history.values():
            try:
                yield player_hist[self.epoch]
            except KeyError:
                continue

    def iter_visible_players_info_by_distance(self) -> Iterator[tuple[characters.ChampionDescription, Coords]]:
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
        self.metastrat_ratings: Dict[str, int] = defaultdict(int)


    def find_next_move_on_path(self, start: Coords, end: Coords) -> Coords | None:
        # returns None if destination is reached
        try:
            path = nx.shortest_path(self.map.graph, source=start, target=end)
            return path[1] if len(path) > 1 else None
        except nx.NetworkXNoPath:
            # happens when end is impassable
            pass
        except nx.NodeNotFound:
            # the end is not in graph ://
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
        except nx.NodeNotFound:
            return None
        except nx.NetworkXNoPath:
            return None


    def get_closest_mist_pos(self) -> Coords | None:
        mist_coords = sorted(self.map.iter_mist_coords(),
                             key=lambda c: manhattan_distance(self.players.own_player_pos, c))
        if mist_coords:
            return mist_coords[0]
        return None


    def update(self, champion_knowledge: characters.ChampionKnowledge, epoch: int):
        self.epoch = epoch
        for ks in self:
            ks.update(champion_knowledge, epoch)


    def reset(self, arena_description: arenas.ArenaDescription):
        for ks in self:
            ks.reset(arena_description)


    def praise(self, score: int, meta_strategy) -> None:
        # meta_strategy should be a MetaStrategy object. Not imported due to circular import
        self.metastrat_ratings[meta_strategy] += score
        meta_strategy.praise(score)


    def __iter__(self) -> Iterator[KnowledgeSource]:
        yield from (self.map, self.players)


    def get_tile_in_direction(self, facing: characters.Facing) -> tiles.TileDescription:
        return self.map.tile_info_at(self.players.own_player_pos + facing.value)


    def get_tile_info_in_front_of(self) -> tiles.TileDescription:
        return self.get_tile_in_direction(self.players.own_player_facing)


    def is_action_possible(self, action: characters.Action) -> bool:
        if action in (characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT,
                      characters.Action.DO_NOTHING, characters.Action.ATTACK):
            return True

        if action is characters.Action.STEP_FORWARD:
            coord = self.players.own_player_pos + self.players.own_player_facing.value
        elif action is characters.Action.STEP_LEFT:
            coord = self.players.own_player_pos + self.players.own_player_facing.turn_left().value
        elif action is characters.Action.STEP_RIGHT:
            coord = self.players.own_player_pos + self.players.own_player_facing.turn_right().value
        elif action is characters.Action.STEP_BACKWARD:
            coord = self.players.own_player_pos + self.players.own_player_facing.opposite().value
        else:
            return False

        return (coord in self.map.graph.nodes and
                self.map.graph.nodes[coord]['type'] not in self.map.impassable_tiles and
                not self.map.graph.nodes[coord]['character'])


    def iter_attacking_coords(self) -> Iterator[Coords]:
        """May return out of map coords."""
        weapon = self.players.own_player_weapon
        self_facing = self.players.own_player_facing
        self_coord = self.players.own_player_pos
        if weapon == 'knife':
            pos = self_coord + self_facing.value
            if pos in self.map.graph.nodes and self.map.graph.nodes[pos]['type'] not in self.map.impassable_tiles:
                yield pos
        elif weapon == 'sword':
            next_tile = self_coord
            for _ in range(3):
                next_tile += self_facing.value
                if next_tile in self.map.graph.nodes and self.map.graph.nodes[next_tile]['type'] == 'wall':
                    break
                yield next_tile
        elif weapon == 'axe':
            center_pos = self_coord + self_facing.value
            for pos in (center_pos,
                        center_pos + self_facing.turn_left().value,
                        center_pos + self_facing.turn_right().value):
                if pos in self.map.graph.nodes and self.map.graph.nodes[pos]['type'] != 'wall':
                    yield pos
        elif weapon.startswith('bow'):
            next_tile = self_coord
            for i in range(1, 50):
                next_tile += self_facing.value
                if next_tile not in self.map.graph.nodes or self.map.graph.nodes[next_tile]['type'] == 'wall':
                    break
                elif next_tile in self.map.graph.nodes and self.map.graph.nodes[next_tile]['type'] == 'sea':
                    continue
                yield next_tile
        elif weapon == 'amulet':
            yield from [self_coord + offset for offset in [
                Coords(1, 1),
                Coords(-1, 1),
                Coords(1, -1),
                Coords(-1, -1),
                Coords(2, 2),
                Coords(-2, 2),
                Coords(2, -2),
                Coords(-2, -2),
            ]]
        else:
            yield from []
