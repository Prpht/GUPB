from gupb.model import characters, coordinates, tiles


class MapMemory:
    def __init__(self):
        self.map_data: dict[coordinates.Coords, tiles.TileDescription] = {}
        self.players: dict[str, coordinates.Coords] = {}
        self.mist_radius: int | None = None
        # Every tile ever seen covered by mist. Mist only ever expands inward, so
        # such a tile stays mist for the rest of the game. Tracking the full set
        # (independent of the menhir and immune to the map-trimming frame filter)
        # lets us always know how close the mist is, even when we can't currently
        # see it and even before the menhir has been located.
        self.mist_seen: set[coordinates.Coords] = set()
        self.observed_mist_distance: float | None = None
        self.menhir_pos: coordinates.Coords | None = None
        self.menhir_verified: bool = False
        self.menhir_estimated_pos: coordinates.Coords | None = None
        self.menhir_confidence: float = 0.0
        self.game_tick: int = 0
        self.mist_tick_counter: int = 0
        self.alive_count: int = 2
        self.last_seen: dict[coordinates.Coords, int] = {}
        self._player_last_seen: dict[str, int] = {}
        self.last_menhir_pos_for_mist: coordinates.Coords | None = None
        self.my_scroll_charges: int = 5
        self.my_weapon: str = "knife"
        self.idle_state: tuple[coordinates.Coords, characters.Facing] | None = None
        self.idle_counter: int = 0

        self._cached_turn_tick: int = -1
        self._turn_nav = None
        self._turn_extract_snapshot: dict | None = None
        self.last_extracted_players: list[coordinates.Coords] = []
        self.firing_positions_exist: dict[coordinates.Coords, bool] = {}

        self._cached_attacked_cells: dict[coordinates.Coords, int] | None = None
        self._return_map_max_forward_time: int = 0
        self._return_map_persistent = None

        self._target_vis_cache: dict = {}
        self._target_vis_cache_ticket = None

        self._combat_arena_cache: dict = {}

    @property
    def player_last_seen(self) -> dict[str, int]:
        return self._player_last_seen

    @property
    def mist_info(self):
        from .mist import MistInfo

        return MistInfo(
            self.menhir_pos,
            self.mist_radius,
            self.mist_tick_counter,
            self.alive_count,
            self.mist_seen,
        )

    def observe(self, knowledge: characters.ChampionKnowledge) -> None:
        from .mist import update_mist_info, filter_memory

        self.game_tick += 1
        self.alive_count = knowledge.no_of_champions_alive

        my_tile = knowledge.visible_tiles.get(knowledge.position)
        new_weapon = "knife"
        if my_tile and my_tile.character:
            new_weapon = my_tile.character.weapon.name
        if new_weapon == "scroll" and self.my_weapon != "scroll":
            self.my_scroll_charges = 5
        self.my_weapon = new_weapon

        current_facing = characters.Facing.UP
        if my_tile and my_tile.character:
            current_facing = my_tile.character.facing
        current_state = (knowledge.position, current_facing)
        if current_state == self.idle_state:
            self.idle_counter += 1
        else:
            self.idle_counter = 0
            self.idle_state = current_state

        for coords, tile_desc in knowledge.visible_tiles.items():
            self.map_data[coords] = tile_desc
            self.last_seen[coords] = self.game_tick

        update_mist_info(self, knowledge)

        self._move_players(knowledge.visible_tiles)
        filter_memory(self, knowledge.position)

    def _move_players(
        self, visible_tiles: dict[coordinates.Coords, tiles.TileDescription]
    ) -> None:
        for coords, tile_desc in visible_tiles.items():
            character = tile_desc.character
            if character is None:
                continue
            previous_coords = self.players.get(character.controller_name)
            if previous_coords is not None and previous_coords != coords:
                self._clear_character_at(previous_coords, character.controller_name)
            self.players[character.controller_name] = coords
            self.player_last_seen[character.controller_name] = self.game_tick

        to_remove = []
        for name, coords in list(self.players.items()):
            visible_tile = visible_tiles.get(coords)
            if visible_tile is not None:
                char = visible_tile.character
                if char is None or char.controller_name != name:
                    to_remove.append((name, coords))
        for name, coords in to_remove:
            del self.players[name]
            self._clear_character_at(coords, name)

        to_remove_unseen = []
        for name, coords in list(self.players.items()):
            if self.game_tick - self.player_last_seen.get(name, self.game_tick) >= 5:
                to_remove_unseen.append((name, coords))
        for name, coords in to_remove_unseen:
            if name in self.players:
                del self.players[name]
            if name in self.player_last_seen:
                del self.player_last_seen[name]
            self._clear_character_at(coords, name)

        if len(self.players) > self.alive_count:
            sorted_players = sorted(
                self.players.items(), key=lambda item: self.last_seen.get(item[1], 0)
            )
            num_to_remove = len(self.players) - self.alive_count
            for i in range(num_to_remove):
                name, coords = sorted_players[i]
                del self.players[name]
                self._clear_character_at(coords, name)

    def _clear_character_at(self, coords: coordinates.Coords, name: str) -> None:
        stale_tile = self.map_data.get(coords)
        if stale_tile is None or stale_tile.character is None:
            return
        if stale_tile.character.controller_name == name:
            self.map_data[coords] = stale_tile._replace(character=None)
