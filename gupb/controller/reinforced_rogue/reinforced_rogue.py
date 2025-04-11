import pickle
import random
import logging

from math import inf
from typing import Optional
from itertools import product

from gupb import controller

from gupb.model import tiles
from gupb.model import arenas
from gupb.model import effects
from gupb.model import weapons
from gupb.model import characters
from gupb.model import consumables
from gupb.model import coordinates

from .constants import DIST_MATRIX_ORDINARY_CHAOS


RANDOM_POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

PACIFIST_POSSIBLE_ACTIONS = [
    # Pacifist gameplay
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    # characters.Action.STEP_BACKWARD, # this has some problems...
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
]

FACINGS = [
    characters.Facing.DOWN,
    characters.Facing.LEFT,
    characters.Facing.RIGHT,
    characters.Facing.UP,
]

DAMAGE: dict[str, int] = {
    "land": 0,
    "sea": +inf,
    "wall": +inf,
    "forest": 0,
    "menhir": 0,
    "mist": effects.MIST_DAMAGE,
    "fire": effects.FIRE_DAMAGE,
    "potion": -consumables.POTION_RESTORED_HP,
    "knife": weapons.Knife.cut_effect().damage,
    "sword": weapons.Sword.cut_effect().damage,
    "bow_loaded": weapons.Bow.cut_effect().damage,
    "bow_unloaded": 0,
    "axe": weapons.Axe.cut_effect().damage,
    "amulet": weapons.Amulet.cut_effect().damage,
    "scroll": 0,
}

BOW_LOADED = weapons.Bow()
BOW_LOADED.ready = True

BOW_UNLOADED = weapons.Bow()
BOW_UNLOADED.ready = False

WEAPONS: dict[str, weapons.Weapon] = {
    "knife": weapons.Knife(),
    "sword": weapons.Sword(),
    "bow_loaded": BOW_LOADED,
    "bow_unloaded": BOW_UNLOADED,
    "axe": weapons.Axe(),
    "amulet": weapons.Amulet(),
    "scroll": weapons.Scroll(),
}

NEIGHBORHOOD_MOORE = [
    coordinates.Coords(0, +1),
    coordinates.Coords(0, -1),
    coordinates.Coords(+1, 0),
    coordinates.Coords(-1, 0),
    coordinates.Coords(+1, +1),
    coordinates.Coords(+1, -1),
    coordinates.Coords(-1, +1),
    coordinates.Coords(-1, -1),
]

NEIGHBORHOOD_VONNEUMMAN = [
    coordinates.Coords(0, +1),
    coordinates.Coords(0, -1),
    coordinates.Coords(+1, 0),
    coordinates.Coords(-1, 0),
]

logger = logging.getLogger("verbose")


# TODO: CONSTANTS
N_LANDMARKS = 8
MENHIR_RADIUS = 8
LANDMARK_RADIUS = 3


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class ReinforcedRogueController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ReinforcedRogueController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    @property
    def name(self) -> str:
        return f"ReinforcedRogueController{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.REINFORCEDROGUE

    def praise(self, score: int) -> None:
        """For now we don't use this."""
        pass

    # =====================================================
    # =====================================================

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena: arenas.Arena = arenas.Arena.load(arena_description.name)
        self.visible_tiles: dict[coordinates.Coords, tiles.TileDescription] = {}

        # Menhir position
        self.menhir: Optional[coordinates.Coords] = None

        # Champion attributes
        self.position: Optional[coordinates.Coords] = None
        self.facing: Optional[characters.Facing] = None
        self.weapon: Optional[weapons.Weapon] = None
        self.health: int = characters.CHAMPION_STARTING_HP

        # Map i.e. the controller's view of the world
        self.map: dict[coordinates.Coords, tiles.TileDescription] = {}

        # Estimated potential damage at any position in the map (computed before taking any action)
        self.potential_damage: dict[coordinates.Coords, int] = {}

        # Visited landmarks i.e. tiles in the map the reveal the unexplored areas
        self.landmarks_visited: dict[coordinates.Coords, bool] = {}

        # Number of steps since we have last seen given tile
        self.last_seen: dict[coordinates.Coords, int] = {}

        # --- Initialize
        for position, tile in self.arena.terrain.items():
            self.map[position] = tile.description()
            self.last_seen[position] = inf

        # --- Compute shortest-paths matrix (Floyd-Warshall)
        # logger.debug(f"Compute shortest-paths matrix (Floyd-Warshall)")
        # self.dist = {u: {v: inf for v in self.map} for u in self.map}

        # for u in self.map:
        #     self.dist[u][u] = 0

        # for u, v in product(self.map, repeat=2):
        #     if (
        #         self.arena.terrain[u].passable
        #         and self.arena.terrain[v].passable
        #         and any(u + facing.value == v for facing in FACINGS)
        #     ):
        #         self.dist[u][v] = 1

        # for k, i, j in product(self.map, repeat=3):
        #     if self.dist[i][j] > (d := self.dist[i][k] + self.dist[k][j]):
        #         self.dist[i][j] = d

        # NOTE: Use precomputed matrix to speed-up experiments
        self.dist = DIST_MATRIX_ORDINARY_CHAOS

        # --- Compute exploration landmarks
        # Greedy approach, no time to think if this is optimal or hard (NP)
        logger.debug(f"Compute exploration landmarks")
        not_seen_positions = set(self.map)

        for _ in range(N_LANDMARKS):
            if len(not_seen_positions) == 0:
                break

            best_position = None
            best_visible = set()

            for position in self.map:
                if self.arena.terrain[position].passable:
                    visible = set()
                    for facing in FACINGS:
                        visible |= set(self.visible_coords(position, facing, WEAPONS["knife"]))
                    if len(not_seen_positions & visible) > len(not_seen_positions & best_visible):
                        best_position = position
                        best_visible = visible

            not_seen_positions -= best_visible
            self.landmarks_visited[best_position] = False

        logger.debug(f"Landmarks {list(self.landmarks_visited.keys())}")
        logger.debug(f"Landmark coverage {1-len(not_seen_positions)/len(self.map):.2%}")

    def simulate_move(
        self,
        position: coordinates.Coords,
        facing: characters.Facing,
        action: characters.Action,
    ) -> tuple[coordinates.Coords, characters.Facing]:
        match action:
            case characters.Action.TURN_LEFT:
                next_position, next_facing = position, facing.turn_left()
            case characters.Action.TURN_RIGHT:
                next_position, next_facing = position, facing.turn_right()
            case characters.Action.STEP_FORWARD:
                next_position, next_facing = position + facing.value, facing
            case characters.Action.STEP_BACKWARD:
                next_position, next_facing = position + facing.opposite().value, facing
            case characters.Action.STEP_LEFT:
                next_position, next_facing = position + facing.turn_left().value, facing
            case characters.Action.STEP_RIGHT:
                next_position, next_facing = position + facing.turn_right().value, facing
            case characters.Action.ATTACK | characters.Action.DO_NOTHING:
                next_position, next_facing = position, facing
        return next_position, next_facing

    def visible_coords(
        self,
        position: coordinates.Coords,
        facing: characters.Facing,
        weapon: weapons.Weapon,
    ) -> list[coordinates.Coords]:
        champion = characters.Champion(position, self.arena)
        champion.facing = facing
        champion.weapon = weapon
        return self.arena.visible_coords(champion)

    def should_attack(self) -> bool:
        for position, tile in self.map.items():
            if (
                self.last_seen[position] == 0
                and tile.type != "forest"
                and tile.character
                and self.health - self.potential_damage[self.position] > 0
                and DAMAGE[self.weapon.description().name] >= self.potential_damage[self.position]
                and any(
                    cut_position == position
                    for cut_position in self.weapon.cut_positions(self.arena.terrain, self.position, self.facing)
                )
            ):
                return True
        return False

    def score(self, action: characters.Action, rand: float) -> tuple[float, ...]:
        next_position, next_facing = self.simulate_move(self.position, self.facing, action)

        health_gain = -inf
        safety_gain = 0
        menhir_gain = 0
        visibility_gain = 0
        exploration_gain = inf

        # TODO: Constant value
        ϵ_visibility = 0.4

        if self.arena.terrain[next_position].passable:
            # Health gain
            # -----------
            health_gain = -self.potential_damage[next_position]

            # Safety gain
            # -----------
            logger.debug("Safety gain")

            for step in NEIGHBORHOOD_VONNEUMMAN:
                if next_position + step in self.map and self.arena.terrain[next_position + step].passable:
                    # Enemies' positions have potential damage `inf` (i.e. we cannot walk into them)
                    # but we don't compute the safety factor for them since we want to be able to
                    # attack
                    damage = self.potential_damage[next_position + step]
                    if damage == inf:
                        damage = 0
                    safety_gain -= damage
            # If we have seen Menhir and potential damage of our position is not 0 then probably
            # it's the mist and we should just move towards the Menhir using the shortest path. This
            # switches the priority of safety and menhir gain in that case.
            safety_gain *= not self.menhir or self.potential_damage[self.position] == 0

            # Menhir distance gain
            # --------------------
            logger.debug("Menhir distance gain")

            if self.menhir:
                menhir_gain = self.dist[next_position][self.menhir]
                # If we have seen Menhir and potential damage of the position we are in is not 0
                # then probably it's mist and we should just move towards the Menhir using the
                # shortest path.
                # Additionally we don't want to stay exactly at Menhir but want to be in its
                # proximity.
                menhir_gain *= not (self.potential_damage[self.position] == 0 and menhir_gain < MENHIR_RADIUS)
                menhir_gain *= -1

            # Exploration gain
            # ----------------
            logger.debug("Exploration gain")

            if not self.menhir:
                for landmark, visited in self.landmarks_visited.items():
                    if not visited:
                        exploration_gain = min(exploration_gain, self.dist[next_position][landmark])
                exploration_gain *= -1
                # `rand` is passed to `score` to denote whether we should prioritize exploatation
                # i.e. moving toward the specified point - Menhir / Landmark or prioritize
                # exploration i.e. incresing visibility
                exploration_gain *= rand < 1 - ϵ_visibility

            # Visibility gain
            # ---------------
            logger.debug("Visibility gain")

            visible = self.visible_coords(next_position, next_facing, self.weapon)

            for position in visible:
                if position in self.map and self.arena.terrain[position].passable and next_position != position:
                    visibility_gain += self.last_seen[position] * 1 / self.dist[next_position][position]

            # TODO: Mobility gain (avoid back alleys)
            # ---------------------------------------
            ...

        logger.debug(f"Action {action} -> {next_position}, {next_facing}")
        logger.debug(f"Health gain = {health_gain}")
        logger.debug(f"Safety gain = {safety_gain}")
        logger.debug(f"Menhir gain = {menhir_gain}")
        logger.debug(f"Explo. gain = {exploration_gain}")
        logger.debug(f"Visib. gain = {visibility_gain}")

        return (health_gain, safety_gain, menhir_gain, exploration_gain, visibility_gain)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            # --- Get visible tiles
            self.visible_tiles = knowledge.visible_tiles

            # --- Get champion's current attributes
            self.position = knowledge.position
            self.weapon = WEAPONS[self.visible_tiles[self.position].character.weapon.name]
            self.facing = self.visible_tiles[self.position].character.facing
            self.health = self.visible_tiles[self.position].character.health

            logger.debug(f"Champion's atrributes")
            logger.debug(f"Position {self.position}")
            logger.debug(f"Facing {self.facing}")
            logger.debug(f"Weapon {self.weapon.description()}")
            logger.debug(f"Health {self.health}")

            # --- Visited landmark?
            # logger.debug(f"Visited landmark?")

            for landmark in self.landmarks_visited:
                if self.dist[self.position][landmark] <= LANDMARK_RADIUS:
                    logger.debug(f"Yes, landmark at {landmark}")
                    self.landmarks_visited[landmark] = True

            # If all landmarks visited and still no menhir then try again visiting landmarks
            if all(self.landmarks_visited.values()) and not self.menhir:
                logger.debug(f"All landmarks visited, but no Menhir :(")
                for landmark in self.landmarks_visited:
                    self.landmarks_visited[landmark] = False

            # --- Update world
            for position, tile in self.visible_tiles.items():
                position = coordinates.Coords(*position)

                # --- Set last-seen-counter to -1 (it gets incremented after this for-loop)
                # logger.debug(f"Set last-seen-counter to -1")
                self.last_seen[position] = -1

                # --- Seen menhir?
                # logger.debug(f"Seen menhir?")
                if tile.type == "menhir":
                    logger.debug(f"Yes, menhir at {position}")
                    self.menhir = position

                # --- Update map
                # logger.debug(f"Update map")
                if position == self.position:
                    tile = tiles.TileDescription(tile.type, tile.loot, None, tile.consumable, tile.effects)

                if character := tile.character:
                    for replace_position, replace_tile in self.map.items():
                        if (
                            replace_tile.character
                            and replace_tile.character.controller_name == character.controller_name
                        ):
                            new_tile = tiles.TileDescription(
                                replace_tile.type,
                                replace_tile.loot,
                                None,
                                replace_tile.consumable,
                                replace_tile.effects,
                            )
                            self.map[replace_position] = new_tile
                            break

                self.map[position] = tile

            # --- Increment last-seen-counter
            # logger.debug(f"Increment last-seen-counter")
            for position in self.map:
                self.last_seen[position] += 1

            # --- Compute potential damage
            # logger.debug(f"Compute potential damage")
            self.potential_damage = {position: 0 for position in self.map}

            for position, tile in self.map.items():
                self.potential_damage[position] += DAMAGE[tile.type]
                self.potential_damage[position] += DAMAGE[tile.consumable.name] if tile.consumable else 0
                self.potential_damage[position] += sum(DAMAGE[effect.type] for effect in tile.effects)
                self.potential_damage[position] += inf if tile.loot and tile.loot.name in ["scroll"] else 0

                # If there is persitent damage at some landmark, mark it as visited.
                if position in self.landmarks_visited and self.potential_damage[position] > 0:
                    self.landmarks_visited[position] = True

                if character := tile.character:
                    # logger.debug(f"Enemy at {position}")
                    self.potential_damage[position] = inf
                    weapon = WEAPONS[character.weapon.name]
                    for cut_position in weapon.cut_positions(self.arena.terrain, position, character.facing):
                        if cut_position in self.map:
                            self.potential_damage[cut_position] += DAMAGE[character.weapon.name]

            # --- ϵ-Greedy action choice
            # logger.debug(f"Choose action")
            # TODO: Constant value
            ϵ = 0.05
            if random.random() < ϵ:
                action = random.choice(PACIFIST_POSSIBLE_ACTIONS)
            else:
                if self.should_attack():
                    action = characters.Action.ATTACK
                else:
                    rand = random.random()
                    scores = {
                        action: (*self.score(action, rand), random.random()) for action in PACIFIST_POSSIBLE_ACTIONS
                    }
                    action = max(scores, key=scores.get)

        except Exception as e:
            # Short circuit in case of failure
            logger.debug(f"WARNING!!! Exception {e}")
            action = random.choice(RANDOM_POSSIBLE_ACTIONS)

        return action


POTENTIAL_CONTROLLERS = [
    ReinforcedRogueController("Rogue"),
]
