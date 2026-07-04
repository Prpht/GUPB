import math
from collections import deque
from typing import List, Optional, Dict, Set, Tuple
from gupb.model import characters
from gupb.model import coordinates


# =============================================================================
#  Stałe i konfiguracja
# =============================================================================

# Typy terenu, po których można chodzić
_WALKABLE_TYPES: Set[str] = {'land', 'forest', 'menhir'}
# Typy terenu przez które "widać" (line-of-sight dla broni liniowych)
_TRANSPARENT_TYPES: Set[str] = {'land', 'menhir', 'sea'}
# Efekty obrażające bota — domyślnie unikane przy pathfindingu
_HAZARD_EFFECTS: Set[str] = {'mist', 'fire'}

# Rankingi broni — wyższy tier = lepsza broń
_WEAPON_TIERS: Dict[str, int] = {
    'knife': 0,
    'axe': 1,
    'sword': 1,
    'amulet': 1,
    'bow': 2,
    'scroll': 2,
}

# Cztery kierunki ruchu (dx, dy)
_DIRECTIONS: List[Tuple[int, int]] = [(0, 1), (0, -1), (1, 0), (-1, 0)]


def _sign(x: int) -> int:
    """Zwraca znak liczby: -1, 0 lub 1."""
    if x > 0:
        return 1
    elif x < 0:
        return -1
    return 0


# =============================================================================
#  Klasa PudzianHeuristics — heurystyki taktyczne i pathfinding
# =============================================================================

class PudzianHeuristics:
    """Zestaw heurystyk ruchu, walki i eksploracji dla bota Pudzian."""

    def __init__(self) -> None:
        # Cache pathfindingu w obrębie JEDNEJ tury — resetowany gdy zmienia się
        # obiekt `knowledge` (czyli na granicy tury). Zero wpływu na zachowanie:
        # te same wejścia dają te same wyniki, cache jedynie eliminuje powtórne
        # budowanie siatki walkable i powtórne BFS w obrębie tej samej decyzji.
        # Patrz _ensure_turn_cache, _build_walkable, _bfs_reachable.
        self._cache_knowledge: Optional[characters.ChampionKnowledge] = None
        self._walkable_cache: Dict[tuple, tuple] = {}
        self._reachable_cache: Dict[tuple, Dict[coordinates.Coords, int]] = {}

    def _ensure_turn_cache(self, knowledge: characters.ChampionKnowledge) -> None:
        """Unieważnia cache pathfindingu na granicy tury.

        `knowledge` to świeży obiekt w każdej turze (NamedTuple budowany przez
        silnik), więc tożsamość obiektu jest pewnym znacznikiem nowej tury.
        Trzymamy referencję, by id() nie zostało wznowione dla innego obiektu.
        """
        if knowledge is not self._cache_knowledge:
            self._cache_knowledge = knowledge
            self._walkable_cache = {}
            self._reachable_cache = {}

    # -------------------------------------------------------------------------
    #  Podstawowe narzędzia
    # -------------------------------------------------------------------------

    @staticmethod
    def dist(p1, p2) -> int:
        """Odległość Manhattan między dwoma punktami."""
        return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

    @staticmethod
    def get_facing(knowledge: characters.ChampionKnowledge) -> Optional[characters.Facing]:
        """Zwraca aktualny kierunek patrzenia bohatera (lub None)."""
        me = knowledge.visible_tiles.get(knowledge.position)
        if me and me.character:
            return me.character.facing
        return None

    @staticmethod
    def _tile_transparent(
        pos: coordinates.Coords,
        knowledge: Optional[characters.ChampionKnowledge],
        terrain_memory: Optional[Dict[coordinates.Coords, str]],
    ) -> Optional[bool]:
        """Zwraca True/False jeśli znamy przejrzystość kafla, None jeśli nieznany."""
        if knowledge and pos in knowledge.visible_tiles:
            tile = knowledge.visible_tiles[pos]
            if tile.type not in _TRANSPARENT_TYPES:
                return False
            return tile.character is None
        if terrain_memory and pos in terrain_memory:
            return terrain_memory[pos] in _TRANSPARENT_TYPES
        return None

    def _line_weapon_has_los(
        self,
        start,
        target,
        facing: characters.Facing,
        reach: int,
        knowledge: Optional[characters.ChampionKnowledge],
        terrain_memory: Optional[Dict[coordinates.Coords, str]],
    ) -> bool:
        """Sprawdza zasięg broni liniowej z uwzględnieniem przeszkód."""
        for r in range(1, reach + 1):
            check = coordinates.Coords(start[0] + facing.value[0] * r, start[1] + facing.value[1] * r)
            if (check[0], check[1]) == (target[0], target[1]):
                return True
            transparent = self._tile_transparent(check, knowledge, terrain_memory)
            if transparent is None or not transparent:
                return False
        return False

    # -------------------------------------------------------------------------
    #  Zasięg broni
    # -------------------------------------------------------------------------

    def is_in_range(
        self,
        start,
        target,
        facing: characters.Facing,
        weapon_name: str,
        knowledge: Optional[characters.ChampionKnowledge] = None,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
    ) -> bool:
        """Sprawdza, czy cel znajduje się w zasięgu danej broni, z uwzględnieniem przeszkód."""
        if knowledge and target not in knowledge.visible_tiles:
            return False

        if 'knife' in weapon_name:
            return self._line_weapon_has_los(start, target, facing, 1, knowledge, terrain_memory)

        if 'sword' in weapon_name:
            return self._line_weapon_has_los(start, target, facing, 3, knowledge, terrain_memory)

        if 'bow' in weapon_name:
            return self._line_weapon_has_los(start, target, facing, 50, knowledge, terrain_memory)

        if 'axe' in weapon_name:
            centre = (start[0] + facing.value[0], start[1] + facing.value[1])
            left = (centre[0] + facing.turn_left().value[0], centre[1] + facing.turn_left().value[1])
            right = (centre[0] + facing.turn_right().value[0], centre[1] + facing.turn_right().value[1])
            return (target[0], target[1]) in [centre, left, right]

        if 'amulet' in weapon_name:
            for r in [1, 2]:
                for sx in [-1, 1]:
                    for sy in [-1, 1]:
                        if (start[0] + sx * r, start[1] + sy * r) == (target[0], target[1]):
                            return True
            return False

        if 'scroll' in weapon_name:
            return self._line_weapon_has_los(start, target, facing, 1, knowledge, terrain_memory)

        return False

    # -------------------------------------------------------------------------
    #  Pathfinding (BFS) z obsługą terrain_memory
    # -------------------------------------------------------------------------

    def _build_walkable(
        self,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]],
        allow_unknown: bool,
        avoid_hazards: bool = True,
    ) -> Tuple[Set[coordinates.Coords], Set[coordinates.Coords], Set[coordinates.Coords], Optional[Tuple[int, int, int, int]]]:
        """Buduje zbiory przejezdnych/zablokowanych pól + pozycje wrogów + opcjonalny bounding box.

        Argumenty
        ---------
        avoid_hazards : bool
            Gdy True (domyślnie), kafle z efektami mgły/ognia idą do `blocked`
            (BFS ich unika). Gdy False — traktowane jak normalny teren walkable
            (używane jako fallback w find_path, gdy bezpieczna ścieżka nie istnieje).

        Współdzielone między find_path i _bfs_reachable, żeby uniknąć duplikacji.

        Memoizowane w obrębie tury: wynik zależy wyłącznie od (knowledge,
        terrain_memory, allow_unknown, avoid_hazards). Zwracamy WSPÓŁDZIELONE
        (nie kopiowane) zbiory — callerzy ich NIE mutują, lecz przekazują pola
        wymuszone jako walkable (start/end/cel) do is_walkable przez `extra`.
        enemy_positions/bounds są tylko czytane.
        """
        self._ensure_turn_cache(knowledge)
        cache_key = (id(terrain_memory), allow_unknown, avoid_hazards)
        cached = self._walkable_cache.get(cache_key)
        if cached is not None:
            return cached

        visible = knowledge.visible_tiles

        enemy_positions: Set[coordinates.Coords] = set()
        for pos, tile in visible.items():
            if tile.character and pos != knowledge.position:
                enemy_positions.add(pos)

        walkable: Set[coordinates.Coords] = set()
        blocked: Set[coordinates.Coords] = set()

        # terrain_memory pamięta TYLKO statyczny typ terenu — nie efekty.
        # Mgła/ogień mogą się więc przedostać przez pamięć, ale jeśli kafel
        # jest aktualnie widoczny, poniższa pętla nadpisze decyzję efektami.
        if terrain_memory:
            for pos, tile_type in terrain_memory.items():
                if tile_type in _WALKABLE_TYPES:
                    walkable.add(pos)
                else:
                    blocked.add(pos)

        for pos, tile in visible.items():
            if tile.type in _WALKABLE_TYPES:
                if avoid_hazards and any(eff.type in _HAZARD_EFFECTS for eff in tile.effects):
                    # Hazard widziany teraz — traktujemy jak ścianę
                    walkable.discard(pos)
                    blocked.add(pos)
                else:
                    walkable.add(pos)
                    blocked.discard(pos)
            else:
                walkable.discard(pos)
                blocked.add(pos)

        walkable -= enemy_positions

        bounds: Optional[Tuple[int, int, int, int]] = None
        if allow_unknown:
            known_positions = walkable | blocked | enemy_positions
            if known_positions:
                bounds = (
                    min(p[0] for p in known_positions),
                    max(p[0] for p in known_positions),
                    min(p[1] for p in known_positions),
                    max(p[1] for p in known_positions),
                )

        result = (walkable, blocked, enemy_positions, bounds)
        self._walkable_cache[cache_key] = result
        return result

    @staticmethod
    def _make_is_walkable(
        walkable: Set[coordinates.Coords],
        blocked: Set[coordinates.Coords],
        bounds: Optional[Tuple[int, int, int, int]],
        extra=frozenset(),
    ):
        """Tworzy closure sprawdzającą przejezdność (z opcjonalnym bounding box).

        `extra` to pola wymuszone jako walkable (start/end/cel). Mają priorytet
        nad `blocked` — zastępują dawne `walkable.add(...)`/`blocked.discard(...)`,
        dzięki czemu zbiory z _build_walkable mogą być współdzielone (bez kopii).
        """
        if bounds is None:
            def check(pos: coordinates.Coords) -> bool:
                return pos in walkable or pos in extra
            return check
        min_x, max_x, min_y, max_y = bounds
        def check(pos: coordinates.Coords) -> bool:
            if pos in extra:
                return True
            if pos in walkable:
                return True
            if pos in blocked:
                return False
            return min_x <= pos[0] <= max_x and min_y <= pos[1] <= max_y
        return check

    def _bfs_find_path(
        self,
        start,
        end,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]],
        allow_unknown: bool,
        avoid_hazards: bool,
    ) -> List[coordinates.Coords]:
        """Pojedynczy BFS z parent-dict (O(V+E)).

        Wewnętrzny helper — caller decyduje czy chce safe path (avoid_hazards=True)
        czy fallback przez mgłę/ogień (False).
        """
        walkable, blocked, enemy_positions, bounds = self._build_walkable(
            knowledge, terrain_memory, allow_unknown, avoid_hazards=avoid_hazards
        )
        # Zbiory z _build_walkable są współdzielone (cache) — nie mutujemy ich,
        # pola wymuszone jako walkable trzymamy w `extra` (priorytet nad blocked).
        # Pozycja startowa musi być zawsze dozwolona — bot fizycznie tam jest.
        extra = {start}

        # end dodajemy WARUNKOWO. Bezwarunkowe dodanie kiedyś powodowało
        # ścieżki kończące się na ścianach. Re-dodajemy gdy end jest wrogiem
        # (combat tactics chcą dojść do jego pola).
        end_tile = knowledge.visible_tiles.get(end)
        if end_tile is not None:
            end_is_walkable_terrain = end_tile.type in _WALKABLE_TYPES
        else:
            end_is_walkable_terrain = (
                terrain_memory is not None
                and end in terrain_memory
                and terrain_memory[end] in _WALKABLE_TYPES
            )
        if end_is_walkable_terrain or end in enemy_positions:
            extra.add(end)

        is_walkable = self._make_is_walkable(walkable, blocked, bounds, extra)

        # Gorąca pętla operuje na zwykłych krotkach (x, y), a nie na Coords
        # (NamedTuple): konstruktor Coords był ~8 mln wywołań / kilka sekund w
        # profilu. Krotka i Coords mają identyczny hash/eq, więc `in walkable`
        # (zbiór Coords) i klucze dict działają tak samo — wynik bit-w-bit ten
        # sam. Do Coords wracamy dopiero przy odbudowie ścieżki (krótka lista).
        s = (start[0], start[1])
        e = (end[0], end[1])
        parents: Dict[tuple, Optional[tuple]] = {s: None}
        queue: deque = deque([s])
        found = False

        while queue:
            curr = queue.popleft()
            if curr == e:
                found = True
                break
            cx, cy = curr
            for dx, dy in _DIRECTIONS:
                next_pos = (cx + dx, cy + dy)
                if next_pos not in parents and is_walkable(next_pos):
                    parents[next_pos] = curr
                    queue.append(next_pos)

        if not found:
            return [start]

        # Odbudowa ścieżki przez backtrack — tu konwersja krotek → Coords.
        path: List[coordinates.Coords] = []
        node: Optional[tuple] = e
        while node is not None:
            path.append(coordinates.Coords(node[0], node[1]))
            node = parents[node]
        path.reverse()
        return path

    def find_path(
        self,
        start,
        end,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
        allow_unknown: bool = False,
    ) -> List[coordinates.Coords]:
        """Znajduje najkrótszą ścieżkę BFS od start do end.

        **Two-tier:**
          1. Najpierw próba ścieżki *bezpiecznej* (omijającej mgłę i ogień).
          2. Gdy nie istnieje — fallback przez hazard (lepsze niż stać w miejscu
             gdy bot musi gdzieś dotrzeć, np. ucieczka do menhira przez mgłę).

        O(V+E) per tier (deque + parent-dict).
        """
        if start == end:
            return [start]

        # Tier 1: safe
        path = self._bfs_find_path(
            start, end, knowledge, terrain_memory, allow_unknown, avoid_hazards=True
        )
        if len(path) > 1:
            return path

        # Tier 2: dopuść mgłę/ogień (ostatnia deska ratunku)
        return self._bfs_find_path(
            start, end, knowledge, terrain_memory, allow_unknown, avoid_hazards=False
        )

    def _bfs_reachable(
        self,
        start,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
        allow_unknown: bool = False,
        avoid_hazards: bool = True,
    ) -> Dict[coordinates.Coords, int]:
        """Single-source BFS — zwraca słownik {cell: distance} dla wszystkich osiągalnych.

        Pozwala uniknąć N×BFS w find_potion/find_weapon_upgrade/find_frontier.
        Domyślnie omija mgłę i ogień (bot nie powinien iść po potkę przez ogień).

        Memoizowane w obrębie tury po (start, terrain_memory, allow_unknown,
        avoid_hazards). find_potion/find_weapon_upgrade/find_frontier wołają to
        z tym samym start=pozycja_bota w jednej turze — bez cache liczyłyby ten
        sam pełnomapowy BFS po 2–3 razy. Zwracany słownik jest TYLKO czytany
        przez callerów (.get), więc bezpiecznie współdzielimy ten sam obiekt.
        """
        self._ensure_turn_cache(knowledge)
        cache_key = (start, id(terrain_memory), allow_unknown, avoid_hazards)
        cached = self._reachable_cache.get(cache_key)
        if cached is not None:
            return cached

        walkable, blocked, _enemy_positions, bounds = self._build_walkable(
            knowledge, terrain_memory, allow_unknown, avoid_hazards=avoid_hazards
        )
        # Zbiory współdzielone (cache) — start wymuszamy przez `extra`, bez mutacji.
        is_walkable = self._make_is_walkable(walkable, blocked, bounds, {start})

        # Gorąca pętla na zwykłych krotkach (x, y) zamiast Coords — patrz nota
        # w _bfs_find_path. Klucze dict są krotkami; callerzy robią distances.get(
        # coords), a krotka i Coords hashują się tak samo, więc wynik identyczny.
        s = (start[0], start[1])
        distances: Dict[tuple, int] = {s: 0}
        queue: deque = deque([s])
        while queue:
            curr = queue.popleft()
            curr_dist = distances[curr]
            cx, cy = curr
            for dx, dy in _DIRECTIONS:
                next_pos = (cx + dx, cy + dy)
                if next_pos not in distances and is_walkable(next_pos):
                    distances[next_pos] = curr_dist + 1
                    queue.append(next_pos)
        self._reachable_cache[cache_key] = distances
        return distances

    # -------------------------------------------------------------------------
    #  Akcja dotarcia do sąsiedniego pola
    # -------------------------------------------------------------------------

    def get_action_to_reach(self, start, target, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Zwraca akcję (obrót lub krok) potrzebną do wejścia na sąsiednie pole."""
        facing = self.get_facing(knowledge)
        if not facing:
            return characters.Action.TURN_LEFT

        expected_dir = (target[0] - start[0], target[1] - start[1])
        if (facing.value[0], facing.value[1]) == expected_dir:
            return characters.Action.STEP_FORWARD

        if facing == characters.Facing.UP:
            return characters.Action.TURN_RIGHT if expected_dir[0] > 0 else characters.Action.TURN_LEFT
        if facing == characters.Facing.DOWN:
            return characters.Action.TURN_LEFT if expected_dir[0] > 0 else characters.Action.TURN_RIGHT
        if facing == characters.Facing.LEFT:
            return characters.Action.TURN_LEFT if expected_dir[1] > 0 else characters.Action.TURN_RIGHT
        if facing == characters.Facing.RIGHT:
            return characters.Action.TURN_RIGHT if expected_dir[1] > 0 else characters.Action.TURN_LEFT
        return characters.Action.TURN_LEFT

    # -------------------------------------------------------------------------
    #  Ruch w kierunku / od celu
    # -------------------------------------------------------------------------

    def _neighbor_passable(
        self,
        pos: coordinates.Coords,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]],
        avoid_chars: bool = True,
        avoid_hazards: bool = True,
    ) -> bool:
        """Czy pojedyncze sąsiednie pole jest realnie przejezdne dla STEP.

        Wspólna, spójna reguła dla move_away / dodge / fallbacków: teren
        walkable, opcjonalnie bez postaci i bez mgły/ognia. Widoczne kafle mają
        priorytet nad pamięcią terenu. W grze `passable = terrain_passable() and
        not character`, więc STEP na pole zajęte/hazard jest po cichu pomijany —
        ten helper zapobiega marnowaniu tury (i wejściu w ogień).
        """
        if pos in knowledge.visible_tiles:
            tile = knowledge.visible_tiles[pos]
            if tile.type not in _WALKABLE_TYPES:
                return False
            if avoid_chars and tile.character is not None:
                return False
            if avoid_hazards and any(eff.type in _HAZARD_EFFECTS for eff in tile.effects):
                return False
            return True
        if terrain_memory and pos in terrain_memory:
            # 'mist' zapamiętana w terrain_memory nie jest w _WALKABLE_TYPES → False
            return terrain_memory[pos] in _WALKABLE_TYPES
        return False

    def move_towards(
        self,
        start,
        end,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
        allow_unknown: bool = False,
    ) -> characters.Action:
        """Wykonuje jeden krok w kierunku celu, korzystając z BFS."""
        path = self.find_path(start, end, knowledge, terrain_memory, allow_unknown=allow_unknown)
        if len(path) > 1:
            return self.get_action_to_reach(start, path[1], knowledge)

        # Fallback: spróbuj kroku, który zbliża do celu
        if allow_unknown:
            known_positions = set(knowledge.visible_tiles.keys())
            if terrain_memory:
                known_positions |= set(terrain_memory.keys())
            known_positions.add(start)
            if known_positions:
                min_x = min(p[0] for p in known_positions)
                max_x = max(p[0] for p in known_positions)
                min_y = min(p[1] for p in known_positions)
                max_y = max(p[1] for p in known_positions)
            else:
                allow_unknown = False
        else:
            min_x = max_x = min_y = max_y = 0

        best_move = None
        best_dist = self.dist(start, end)
        for dx, dy in _DIRECTIONS:
            candidate = coordinates.Coords(start[0] + dx, start[1] + dy)
            passable = False
            if candidate in knowledge.visible_tiles or (terrain_memory and candidate in terrain_memory):
                passable = self._neighbor_passable(
                    candidate, knowledge, terrain_memory,
                    avoid_chars=True, avoid_hazards=True,
                )
            elif allow_unknown:
                passable = min_x <= candidate[0] <= max_x and min_y <= candidate[1] <= max_y
            if passable:
                d = self.dist(candidate, end)
                if d < best_dist:
                    best_dist = d
                    best_move = candidate
        if best_move is not None:
            return self.get_action_to_reach(start, best_move, knowledge)
        return characters.Action.TURN_LEFT

    def move_away(
        self,
        start,
        avoid,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
    ) -> characters.Action:
        """Wykonuje jeden krok w kierunku ODDALONYM od pozycji avoid.

        Sprawdza zarówno widoczne kafelki, jak i terrain_memory.
        """
        possible_moves = [
            coordinates.Coords(start[0], start[1] + 1),
            coordinates.Coords(start[0], start[1] - 1),
            coordinates.Coords(start[0] + 1, start[1]),
            coordinates.Coords(start[0] - 1, start[1]),
        ]
        best_move, max_d = start, self.dist(start, avoid)

        # Pass 1: pola bez postaci i bez mgły/ognia (preferowane). Pass 2 (gdy
        # nic nie znaleziono): dopuść hazard — lepiej uciec przez mgłę niż stać.
        for avoid_hazards in (True, False):
            for move in possible_moves:
                if not self._neighbor_passable(
                    move, knowledge, terrain_memory,
                    avoid_chars=True, avoid_hazards=avoid_hazards,
                ):
                    continue
                d = self.dist(move, avoid)
                if d > max_d:
                    max_d, best_move = d, move
            if best_move != start:
                break

        if best_move != start:
            facing = self.get_facing(knowledge)
            if facing is not None:
                move_dir = (best_move[0] - start[0], best_move[1] - start[1])
                fv = (facing.value[0], facing.value[1])
                # Strafe gdy się da — zachowuje twarz ku wrogowi (możliwy
                # kontratak/strzał). Bez tego ruch prostopadły wpadał w
                # get_action_to_reach, które OBRACAŁO bota bokiem/plecami do
                # wroga (i marnowało turę). Mirror logiki z dodge_perpendicular.
                if move_dir == fv:
                    return characters.Action.STEP_FORWARD
                if move_dir == (-fv[0], -fv[1]):
                    return characters.Action.STEP_BACKWARD
                if move_dir == (facing.turn_left().value[0], facing.turn_left().value[1]):
                    return characters.Action.STEP_LEFT
                if move_dir == (facing.turn_right().value[0], facing.turn_right().value[1]):
                    return characters.Action.STEP_RIGHT
            return self.get_action_to_reach(start, best_move, knowledge)

        # Brak kierunku oddalającego — spróbuj cofnąć się, by wyrwać się
        # z uwięzienia przy ścianie (lepsze niż TURN_RIGHT w pętli).
        facing = self.get_facing(knowledge)
        if facing is not None:
            back = coordinates.Coords(start[0] - facing.value[0], start[1] - facing.value[1])
            back_walkable = False
            if back in knowledge.visible_tiles:
                tile = knowledge.visible_tiles[back]
                back_walkable = tile.type in _WALKABLE_TYPES and tile.character is None
            elif terrain_memory and back in terrain_memory:
                back_walkable = terrain_memory[back] in _WALKABLE_TYPES
            if back_walkable:
                return characters.Action.STEP_BACKWARD
        return characters.Action.TURN_RIGHT

    # -------------------------------------------------------------------------
    #  Szukanie łupów i mikstur
    # -------------------------------------------------------------------------

    def find_potion(
        self,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
        allow_unknown: bool = False,
    ) -> Optional[coordinates.Coords]:
        """Zwraca pozycję najbliższej OSIĄGALNEJ mikstury (consumable).

        Używa pojedynczego BFS od pozycji bota zamiast N×BFS (raz na kandydata).
        """
        candidates = [
            pos for pos, tile in knowledge.visible_tiles.items()
            if pos != knowledge.position and tile.consumable and not tile.character
        ]
        if not candidates:
            return None

        distances = self._bfs_reachable(
            knowledge.position, knowledge, terrain_memory, allow_unknown=allow_unknown
        )

        best_pos = None
        min_dist = float('inf')
        for pos in candidates:
            d = distances.get(pos)
            if d is not None and d < min_dist:
                min_dist = d
                best_pos = pos
        return best_pos

    def find_weapon_upgrade(
        self,
        start,
        knowledge: characters.ChampionKnowledge,
        current_weapon: str,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
        allow_unknown: bool = False,
    ) -> Optional[coordinates.Coords]:
        """Zwraca pozycję najbliższej widocznej i OSIĄGALNEJ broni będącej ulepszeniem.

        Używa pojedynczego BFS od start zamiast N×BFS (raz na kandydata).
        """
        current_tier = _WEAPON_TIERS.get(current_weapon, 0)

        candidates: List[coordinates.Coords] = []
        for pos, tile in knowledge.visible_tiles.items():
            if pos == start:
                continue
            if tile.loot and not tile.character:
                loot_name = tile.loot.name
                # Normalizacja: 'bow_loaded'/'bow_unloaded' → 'bow'
                if loot_name.startswith('bow'):
                    loot_name = 'bow'
                if _WEAPON_TIERS.get(loot_name, 0) > current_tier:
                    candidates.append(pos)

        if not candidates:
            return None

        distances = self._bfs_reachable(
            start, knowledge, terrain_memory, allow_unknown=allow_unknown
        )

        best_pos = None
        min_dist = float('inf')
        for pos in candidates:
            d = distances.get(pos)
            if d is not None and d < min_dist:
                min_dist = d
                best_pos = pos
        return best_pos

    # -------------------------------------------------------------------------
    #  Obozowanie (idle avoidance)
    # -------------------------------------------------------------------------

    def camp(self) -> characters.Action:
        """Obrót w celu uniknięcia Idle Penalty i skanowania okolicy."""
        return characters.Action.TURN_RIGHT

    # -------------------------------------------------------------------------
    #  Unik prostopadły (dodge)
    # -------------------------------------------------------------------------

    def dodge_perpendicular(
        self,
        pos,
        enemy_pos,
        direction: str,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
    ) -> characters.Action:
        """Unik prostopadły do osi łączącej gracza z wrogiem.

        direction: 'left' lub 'right' — preferowany kierunek uniku.
        Jeśli preferowany kierunek jest zablokowany, próbuje przeciwny.
        Gdy oba zablokowane — próbuje STEP_BACKWARD (jeśli przejezdne),
        ostatecznie obraca się w lewo.
        """
        dx = enemy_pos[0] - pos[0]
        dy = enemy_pos[1] - pos[1]

        # Gwarancja, że wektory są ortogonalne (tylko ruch pion/poziom).
        # Poprzednia implementacja ze znakami mogła zwrócić wektor ukośny (np. (-1, 1)),
        # przez co get_action_to_reach pętliło się obracając bota bez końca.
        if abs(dx) > abs(dy):
            perp_left = coordinates.Coords(0, -_sign(dx))
            perp_right = coordinates.Coords(0, _sign(dx))
        else:
            perp_left = coordinates.Coords(_sign(dy), 0)
            perp_right = coordinates.Coords(-_sign(dy), 0)

        if direction == 'left':
            primary, secondary = perp_left, perp_right
        else:
            primary, secondary = perp_right, perp_left

        facing = self.get_facing(knowledge)

        for offset in (primary, secondary):
            target = coordinates.Coords(pos[0] + offset[0], pos[1] + offset[1])
            # Pole zajęte przez postać lub z mgłą/ogniem → unik tam to stracona
            # tura (STEP no-op) lub wejście w ogień. Odrzucamy, próbujemy drugi.
            if not self._neighbor_passable(
                target, knowledge, terrain_memory,
                avoid_chars=True, avoid_hazards=True,
            ):
                continue

            if facing is None:
                return self.get_action_to_reach(pos, target, knowledge)

            move = (offset[0], offset[1])
            fv = (facing.value[0], facing.value[1])
            if move == fv:
                return characters.Action.STEP_FORWARD
            if move == (-fv[0], -fv[1]):
                return characters.Action.STEP_BACKWARD
            if move == (facing.turn_left().value[0], facing.turn_left().value[1]):
                return characters.Action.STEP_LEFT
            if move == (facing.turn_right().value[0], facing.turn_right().value[1]):
                return characters.Action.STEP_RIGHT
            return self.get_action_to_reach(pos, target, knowledge)

        # Oba kierunki prostopadłe zablokowane — spróbuj STEP_BACKWARD.
        # Bot przy ścianie z wrogiem przed sobą inaczej oscyluje TURN_LEFT
        # z mask blokującą drugi DODGE.
        if facing is not None:
            back = coordinates.Coords(pos[0] - facing.value[0], pos[1] - facing.value[1])
            back_walkable = False
            if back in knowledge.visible_tiles:
                tile = knowledge.visible_tiles[back]
                back_walkable = tile.type in _WALKABLE_TYPES and tile.character is None
            elif terrain_memory and back in terrain_memory:
                back_walkable = terrain_memory[back] in _WALKABLE_TYPES
            if back_walkable:
                return characters.Action.STEP_BACKWARD

        return characters.Action.TURN_LEFT

    # -------------------------------------------------------------------------
    #  Wyrównanie do osi (align) — przydatne przy broni dystansowej
    # -------------------------------------------------------------------------

    def align_to_diagonal(
        self,
        pos,
        enemy_pos,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
    ) -> characters.Action:
        """Pozycjonuje bota na przekątnej względem wroga (atak amuletem).

        Amulet trafia na pozycje (±r, ±r) względem atakującego, r∈{1,2}.
        Szukamy więc pozycji będących (±r, ±r) względem WROGA — to miejsca
        skąd bot może zaatakować. Preferujemy r=1 (bliżej = bezpieczniej).
        """
        candidates = []
        for r in [1, 2]:
            for sx in [-1, 1]:
                for sy in [-1, 1]:
                    diag = coordinates.Coords(
                        enemy_pos[0] + sx * r,
                        enemy_pos[1] + sy * r,
                    )
                    tile = knowledge.visible_tiles.get(diag)
                    if tile:
                        walkable = tile.type in _WALKABLE_TYPES and not tile.character
                    elif terrain_memory and diag in terrain_memory:
                        walkable = terrain_memory[diag] in _WALKABLE_TYPES
                    else:
                        walkable = False
                    if walkable:
                        candidates.append(diag)

        if not candidates:
            return self.move_towards(pos, enemy_pos, knowledge, terrain_memory)

        best = min(candidates, key=lambda c: self.dist(pos, c))
        if best == pos:
            # Bot już stoi na diagonali. Amulet trafia na (±r, ±r) niezależnie
            # od facing'u, ale jeśli możemy, atakujemy zamiast obracać się.
            cf = self.get_facing(knowledge)
            if cf is not None:
                return characters.Action.ATTACK
            return characters.Action.TURN_RIGHT
        return self.move_towards(pos, best, knowledge, terrain_memory)

    # Kolejność zgodna z ruchem wskazówek zegara (TURN_RIGHT)
    _FACING_CW = [
        characters.Facing.UP,
        characters.Facing.RIGHT,
        characters.Facing.DOWN,
        characters.Facing.LEFT,
    ]

    def _optimal_turn(
        self,
        current: characters.Facing,
        targets: List[characters.Facing],
    ) -> characters.Action:
        """Zwraca TURN_LEFT lub TURN_RIGHT prowadzące do nearest target w min. krokach.

        Zakłada że `current` NIE jest w targets (caller powinien sprawdzić wcześniej).
        Defensywnie: jeśli już patrzymy w docelowy kierunek — atakujemy zamiast
        wracać domyślny TURN_RIGHT (poprzednia wersja kręciła botem bez sensu).
        """
        if current in targets:
            return characters.Action.ATTACK

        ci = self._FACING_CW.index(current)
        best_cost = 4
        best_action = characters.Action.TURN_RIGHT
        for target in targets:
            ti = self._FACING_CW.index(target)
            right = (ti - ci) % 4
            left = (4 - right) % 4
            if right < best_cost:
                best_cost = right
                best_action = characters.Action.TURN_RIGHT
            if left < best_cost:
                best_cost = left
                best_action = characters.Action.TURN_LEFT
        return best_action

    def align_to_adjacent(
        self,
        pos,
        enemy_pos,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
    ) -> characters.Action:
        """Pozycjonuje bota na dowolnym z 8 pól przyległych do wroga (dla siekiery).

        Siekiera bije T-kształt (środek + lewy + prawy od kierunku patrzenia),
        co oznacza że każde z 8 otaczających pól jest prawidłową pozycją ataku.
        Gdy bot jest już przyległy, obraca się optymalnie (min. kroków) tak by
        wróg znalazł się w T-kształcie — zamiast zawsze TURN_RIGHT.
        """
        candidates = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                adj = coordinates.Coords(enemy_pos[0] + dx, enemy_pos[1] + dy)
                if adj == pos:
                    candidates.append(adj)
                    continue
                tile = knowledge.visible_tiles.get(adj)
                if tile:
                    walkable = tile.type in _WALKABLE_TYPES and not tile.character
                elif terrain_memory and adj in terrain_memory:
                    walkable = terrain_memory[adj] in _WALKABLE_TYPES
                else:
                    walkable = False
                if walkable:
                    candidates.append(adj)

        if not candidates:
            return self.move_towards(pos, enemy_pos, knowledge, terrain_memory)

        best = min(candidates, key=lambda c: self.dist(pos, c))
        if best != pos:
            return self.move_towards(pos, best, knowledge, terrain_memory)

        # Bot już jest przyległy — oblicz kierunek który wstawia wroga w T-kształt.
        # T-kształt: środek = 1 krok w przód, lewy i prawy = skosy przed botem.
        # Wróg jest w T gdy: dy<0 → UP, dy>0 → DOWN, dx<0 → LEFT, dx>0 → RIGHT.
        ddx = enemy_pos[0] - pos[0]
        ddy = enemy_pos[1] - pos[1]
        valid_facings = []
        if ddy < 0:
            valid_facings.append(characters.Facing.UP)
        if ddy > 0:
            valid_facings.append(characters.Facing.DOWN)
        if ddx < 0:
            valid_facings.append(characters.Facing.LEFT)
        if ddx > 0:
            valid_facings.append(characters.Facing.RIGHT)

        current_facing = self.get_facing(knowledge)
        if not valid_facings or current_facing is None:
            return characters.Action.TURN_RIGHT

        # Bot już patrzy w stronę pozwalającą trafić — nie kręć się, atakuj.
        # Bez tego guarda _optimal_turn zwracało TURN_RIGHT nawet gdy
        # current_facing ∈ valid_facings (default best_action), marnując turę.
        if current_facing in valid_facings:
            return characters.Action.ATTACK

        return self._optimal_turn(current_facing, valid_facings)

    def align_to_axis(
        self,
        pos,
        enemy_pos,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
        weapon_name: str = 'sword',
    ) -> characters.Action:
        """Znajduje najbliższe przejezdne pole na tej samej osi X lub Y co wróg.

        Przeszukuje BFS od pozycji gracza, filtrując pola, które
        współdzielą współrzędną X lub Y z pozycją wroga.
        Dla broni liniowych wybiera tylko takie pola, z których istnieje
        realny LOS (is_in_range) do celu.
        """
        # Zbiór przejezdnych pól spójny z find_path: omija widoczną mgłę/ogień
        # i mgłę zapamiętaną w terrain_memory, wyklucza inne postacie.
        # (Wcześniej align_to_axis budował własny zbiór ignorujący hazardy —
        # ALIGN_AXIS jest dozwolone nawet przy mgle, więc bot ustawiał się do
        # strzału idąc przez strefę śmierci.)
        walkable, _blocked, _enemies, _bounds = self._build_walkable(
            knowledge, terrain_memory, allow_unknown=False, avoid_hazards=True
        )
        # walkable jest współdzielone (cache) — nie mutujemy; pola wymuszone
        # (start + pole wroga, dozwolone w walce) trzymamy lokalnie.
        force = (pos, enemy_pos)

        # BFS szukający pola na osi wroga (deque — O(1) popleft)
        queue: deque = deque([pos])
        visited: Set[coordinates.Coords] = {pos}

        while queue:
            curr = queue.popleft()

            # Sprawdź czy curr jest dobrym celem (na osi z czystym LOS).
            # WAŻNE: niezależnie od wyniku LOS-check, kontynuujemy ekspansję
            # sąsiadów poniżej. Wcześniejsza wersja używała `continue` po
            # zwalonym LOS, przez co BFS kończył się od razu gdy bot startował
            # na osi wroga ze ścianą na linii strzału — bot zwracał TURN_LEFT
            # i kręcił się w miejscu zamiast szukać innej pozycji ataku.
            if curr[0] == enemy_pos[0] or curr[1] == enemy_pos[1]:
                if curr == enemy_pos:
                    return self.move_towards(pos, curr, knowledge, terrain_memory)
                los_ok = True
                if weapon_name in ('knife', 'sword', 'bow', 'scroll'):
                    if curr[0] == enemy_pos[0]:
                        facing = characters.Facing.UP if enemy_pos[1] < curr[1] else characters.Facing.DOWN
                    else:
                        facing = characters.Facing.LEFT if enemy_pos[0] < curr[0] else characters.Facing.RIGHT
                    los_ok = self.is_in_range(
                        curr, enemy_pos, facing, weapon_name, knowledge, terrain_memory
                    )
                if los_ok:
                    if curr == pos:
                        # Bot już stoi w idealnym miejscu — musi się obrócić do wroga.
                        # move_towards(pos, pos) zwraca TURN_LEFT (brak ścieżki do siebie),
                        # co powoduje oscylację lewo-prawo. Oblicz wymagany facing i obróć.
                        if curr[0] == enemy_pos[0]:
                            req_facing = (
                                characters.Facing.UP if enemy_pos[1] < curr[1]
                                else characters.Facing.DOWN
                            )
                        else:
                            req_facing = (
                                characters.Facing.LEFT if enemy_pos[0] < curr[0]
                                else characters.Facing.RIGHT
                            )
                        cf = self.get_facing(knowledge)
                        if cf is not None and cf != req_facing:
                            return self._optimal_turn(cf, [req_facing])
                        return characters.Action.ATTACK  # safety: facing ok, auto-attack should've fired
                    return self.move_towards(pos, curr, knowledge, terrain_memory)

            for dx, dy in _DIRECTIONS:
                next_pos = coordinates.Coords(curr[0] + dx, curr[1] + dy)
                if next_pos not in visited and (next_pos in walkable or next_pos in force):
                    visited.add(next_pos)
                    queue.append(next_pos)

        # Nie znaleziono — obracamy się
        return characters.Action.TURN_LEFT

    # -------------------------------------------------------------------------
    #  Utrzymanie optymalnego dystansu
    # -------------------------------------------------------------------------

    def maintain_distance(
        self,
        pos,
        enemy_pos,
        optimal_range: int,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
        weapon_name: str = 'sword',
    ) -> characters.Action:
        """Utrzymuje optymalny dystans od wroga.

        Optymalne zakresy broni: knife=1, sword=2, axe=1, bow=5, amulet=1, scroll=1.
        Jeśli za blisko — ucieka. Jeśli za daleko — podchodzi.
        W idealnym zakresie — wyrównuje się do pozycji ataku adekwatnie do broni:
          • amulet → align_to_diagonal (atak po skosie r∈{1,2})
          • axe    → align_to_adjacent (T-shape, dowolny z 8 sąsiadów wroga)
          • inne   → align_to_axis (broń liniowa: knife/sword/bow/scroll)
        """
        current_dist = self.dist(pos, enemy_pos)

        if current_dist < optimal_range:
            # Za blisko — uciekamy (głównie dla bow przy szarżującym wrogu)
            return self.move_away(pos, enemy_pos, knowledge, terrain_memory)
        elif current_dist > optimal_range + 2:
            # Za daleko — podchodzimy
            return self.move_towards(pos, enemy_pos, knowledge, terrain_memory)

        # Idealny dystans — wyrównujemy się do odpowiedniej pozycji ataku
        if weapon_name == 'amulet':
            return self.align_to_diagonal(pos, enemy_pos, knowledge, terrain_memory)
        if weapon_name == 'axe':
            return self.align_to_adjacent(pos, enemy_pos, knowledge, terrain_memory)
        return self.align_to_axis(pos, enemy_pos, knowledge, terrain_memory, weapon_name=weapon_name)

    # -------------------------------------------------------------------------
    #  Eksploracja — szukanie granicy (frontier)
    # -------------------------------------------------------------------------

    def find_frontier(
        self,
        pos,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Dict[coordinates.Coords, str],
        visited_counter: Optional[Dict[coordinates.Coords, int]] = None,
        menhir_hint: Optional[coordinates.Coords] = None,
    ) -> Optional[coordinates.Coords]:
        """Zwraca najlepszą OSIĄGALNĄ komórkę graniczną (frontier).

        Frontier to przejezdna komórka w terrain_memory, która posiada
        co najmniej jednego sąsiada NIEOBECNEGO w terrain_memory.

        Scoring (mniejszy = lepszy):
          score = dystans_BFS
                + 2 × wizyty_na_polu                    (anty-oscylacja)
                + 0.5 × wizyty_sąsiadów                 (omijaj wydeptane okolice)
                − bonus_za_zbliżenie_do_menhira         (jeśli podpowiedź podana)
                − liczba_nieznanych_sąsiadów            (information gain)

        Argumenty
        ---------
        visited_counter : Dict[Coords, int], optional
            Licznik wizyt bota na każdym polu — penalizuje powtórki.
        menhir_hint : Coords, optional
            Oszacowana pozycja menhira (z geometrii mgły).
            Frontier zbliżający do tej pozycji dostaje bonus.

        Używa pojedynczego BFS od `pos` (O(V+E)).
        """
        # Wszystkie cele-kandydaci + liczba nieznanych sąsiadów (information gain)
        candidates: List[Tuple[coordinates.Coords, int]] = []
        for cell, tile_type in terrain_memory.items():
            if tile_type not in _WALKABLE_TYPES:
                continue
            unknown_neighbors = 0
            for dx, dy in _DIRECTIONS:
                neighbor = coordinates.Coords(cell[0] + dx, cell[1] + dy)
                if neighbor not in terrain_memory:
                    unknown_neighbors += 1
            if unknown_neighbors > 0:
                candidates.append((cell, unknown_neighbors))

        if not candidates:
            return None

        distances = self._bfs_reachable(
            pos, knowledge, terrain_memory, allow_unknown=True
        )

        current_menhir_dist = (
            self.dist(pos, menhir_hint) if menhir_hint is not None else 0
        )

        best_pos = None
        best_score = float('inf')

        for cell, unknown_neighbors in candidates:
            d = distances.get(cell)
            if d is None or d == 0:  # nieosiągalny lub == pos
                continue

            score = float(d)

            # Penalizacja za wcześniejsze wizyty (samo pole + sąsiedzi)
            if visited_counter is not None:
                score += 2.0 * visited_counter.get(cell, 0)
                for dx, dy in _DIRECTIONS:
                    neigh = coordinates.Coords(cell[0] + dx, cell[1] + dy)
                    score += 0.5 * visited_counter.get(neigh, 0)

            # Bonus za zbliżenie do oszacowanego menhira
            if menhir_hint is not None:
                cell_menhir_dist = self.dist(cell, menhir_hint)
                # delta < 0 = zbliżamy się; odejmujemy od score (bonus)
                score += (cell_menhir_dist - current_menhir_dist) * 0.5

            # Information gain — frontier z większą "powierzchnią" nieznanego
            score -= 0.5 * unknown_neighbors

            if score < best_score:
                best_score = score
                best_pos = cell

        return best_pos

    # -------------------------------------------------------------------------
    #  Analiza kierunku patrzenia wroga
    # -------------------------------------------------------------------------

    @staticmethod
    def enemy_facing_towards(my_pos, enemy_pos, enemy_facing: characters.Facing) -> bool:
        """Sprawdza, czy wróg patrzy w naszym kierunku.

        Zwraca True tylko gdy facing wroga zgadza się ze znakiem na OSI
        DOMINUJĄCEJ (większa |delta|). Poprzednia wersja sprawdzała OR na obu
        osiach — wróg patrzący w bok (np. RIGHT, gdy jesteśmy głównie nad nim)
        fałszywie raportował "celuje w nas", zaszumiając cechę stanu.
        """
        dx = my_pos[0] - enemy_pos[0]
        dy = my_pos[1] - enemy_pos[1]
        fv = enemy_facing.value

        if abs(dx) >= abs(dy):
            return fv[0] != 0 and _sign(dx) == _sign(fv[0])
        return fv[1] != 0 and _sign(dy) == _sign(fv[1])

    # -------------------------------------------------------------------------
    #  Kompas mgły — kierunek ucieczki od mist
    # -------------------------------------------------------------------------

    def compute_mist_compass(
        self,
        knowledge: characters.ChampionKnowledge,
    ) -> Tuple[float, float]:
        """Oblicza wektor kompasu mgły — kierunek OD centroidu mgły.

        Znajduje wszystkie widoczne kafelki mgły (mist), oblicza
        ich centroid i zwraca znormalizowany wektor od centroidu
        do pozycji gracza. Wartości w zakresie [-1, 1].
        Jeśli brak mgły w polu widzenia — zwraca (0.0, 0.0).
        """
        mist_tiles: List[coordinates.Coords] = []

        for pos, tile in knowledge.visible_tiles.items():
            if any(eff.type == 'mist' for eff in tile.effects):
                mist_tiles.append(pos)

        if not mist_tiles:
            return (0.0, 0.0)

        # Centroid mgły
        cx = sum(p[0] for p in mist_tiles) / len(mist_tiles)
        cy = sum(p[1] for p in mist_tiles) / len(mist_tiles)

        # Wektor od centroidu do gracza
        my_pos = knowledge.position
        vx = my_pos[0] - cx
        vy = my_pos[1] - cy

        magnitude = math.sqrt(vx * vx + vy * vy)
        if magnitude == 0:
            return (0.0, 0.0)

        return (vx / magnitude, vy / magnitude)

    # -------------------------------------------------------------------------
    #  Oszacowanie pozycji menhiru z geometrii mgły
    # -------------------------------------------------------------------------

    def estimate_menhir_from_mist(
        self,
        knowledge: characters.ChampionKnowledge,
    ) -> Optional[coordinates.Coords]:
        """Oszacuj pozycję menhiru na podstawie widocznej mgły.

        Mgła w GUPB tworzy skurczający się okrąg wokół menhiru.
        Bot znajduje się wewnątrz strefy bezpiecznej, a widoczne kratki
        mgły to brzeg tej strefy — punkty na okręgu wokół menhiru.

        Założenia heurystyki:
          * Bot jest w przybliżeniu wewnątrz strefy bezpiecznej.
          * Widoczna mgła to fragment okręgu — jego centroid wskazuje
            kierunek brzegu strefy najbliższy botowi.
          * Menhir jest po przeciwnej stronie centroidu mgły względem bota,
            w przybliżeniu w odległości równej dystansowi bota do centroidu
            (założenie: bot ≈ w połowie promienia strefy).

        Zwraca szacunkowy Coords lub None gdy brak widocznej mgły
        albo mgła otacza bota symetrycznie (centroid ≈ pozycja bota).
        """
        mist_tiles: List[coordinates.Coords] = [
            pos for pos, tile in knowledge.visible_tiles.items()
            if any(eff.type == 'mist' for eff in tile.effects)
        ]

        if not mist_tiles:
            return None

        cx = sum(p[0] for p in mist_tiles) / len(mist_tiles)
        cy = sum(p[1] for p in mist_tiles) / len(mist_tiles)

        bot_x, bot_y = knowledge.position[0], knowledge.position[1]
        # Wektor od centroidu mgły do bota = kierunek "do środka strefy"
        vx = bot_x - cx
        vy = bot_y - cy

        # Mgła otacza bota symetrycznie → brak użytecznego kierunku
        if vx * vx + vy * vy < 1.0:
            return None

        # Menhir = lustro centroidu mgły względem bota
        estimate_x = int(round(bot_x + vx))
        estimate_y = int(round(bot_y + vy))

        return coordinates.Coords(estimate_x, estimate_y)

    # -------------------------------------------------------------------------
    #  Ucieczka od mgły (bez znajomości menhiru)
    # -------------------------------------------------------------------------

    def move_away_from_mist(
        self,
        pos,
        knowledge: characters.ChampionKnowledge,
        terrain_memory: Optional[Dict[coordinates.Coords, str]] = None,
    ) -> characters.Action:
        """Ucieczka od mgły — wybiera sąsiednie pole najdalsze od centroidu mgły.

        Używane gdy bot nie zna pozycji menhiru i musi uciekać
        od mgły w oparciu o lokalne informacje.
        W przeciwieństwie do kompasowego podejścia, wybiera
        KONKRETNE sąsiednie pole (zamiast celu 10 kratek dalej),
        więc BFS zawsze znajdzie ścieżkę.
        """
        mist_tiles = [
            p for p, tile in knowledge.visible_tiles.items()
            if any(eff.type == 'mist' for eff in tile.effects)
        ]

        if not mist_tiles:
            return characters.Action.TURN_LEFT

        # Centroid mgły
        cx = sum(p[0] for p in mist_tiles) / len(mist_tiles)
        cy = sum(p[1] for p in mist_tiles) / len(mist_tiles)
        mist_center = coordinates.Coords(int(cx), int(cy))

        # Wybierz sąsiednie przejezdne pole najdalsze od centroidu mgły
        possible_moves = [
            coordinates.Coords(pos[0] + dx, pos[1] + dy)
            for dx, dy in _DIRECTIONS
        ]

        best_move = None
        max_d = -1

        for move in possible_moves:
            passable = False
            if move in knowledge.visible_tiles:
                tile = knowledge.visible_tiles[move]
                if tile.type in _WALKABLE_TYPES and tile.character is None:
                    # Unikaj kratek z mgłą
                    has_mist = any(eff.type == 'mist' for eff in tile.effects)
                    passable = not has_mist
            elif terrain_memory and move in terrain_memory:
                if terrain_memory[move] in _WALKABLE_TYPES:
                    passable = True

            if passable:
                d = self.dist(move, mist_center)
                if d > max_d:
                    max_d = d
                    best_move = move

        if best_move:
            return self.get_action_to_reach(pos, best_move, knowledge)

        # Brak bezpiecznych pól — wybierz "najmniej złe" sąsiednie pole
        fallback_move = None
        best_score = -1_000
        for move in possible_moves:
            passable = False
            has_mist = False
            has_fire = False
            if move in knowledge.visible_tiles:
                tile = knowledge.visible_tiles[move]
                if tile.type in _WALKABLE_TYPES:
                    passable = True
                    has_mist = any(eff.type == 'mist' for eff in tile.effects)
                    has_fire = any(eff.type == 'fire' for eff in tile.effects)
            elif terrain_memory and move in terrain_memory:
                passable = terrain_memory[move] in _WALKABLE_TYPES
            if not passable:
                continue
            penalty = (5 if has_mist else 0) + (8 if has_fire else 0)
            score = self.dist(move, mist_center) - penalty
            if score > best_score:
                best_score = score
                fallback_move = move

        if fallback_move:
            return self.get_action_to_reach(pos, fallback_move, knowledge)

        # Beznadziejnie zablokowany — przynajmniej rotuj
        return characters.Action.TURN_LEFT
