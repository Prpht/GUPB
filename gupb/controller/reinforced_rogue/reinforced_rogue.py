import random
import logging

from math import inf
from typing import Optional
from queue import PriorityQueue
from collections import defaultdict

from gupb import controller

from gupb.model import tiles
from gupb.model import arenas
from gupb.model import weapons
from gupb.model import characters
from gupb.model import coordinates

from .constants import *

logger = logging.getLogger("verbose")


def taxicab_dist(a: coordinates.Coords, b: coordinates.Coords) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


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
        pass

    # ==============================================================================================
    # ==============================================================================================

    def passable(self, position: coordinates.Coords) -> bool:
        return self.arena.terrain[position].passable and not self.map[position].character

    def neigbors(self, position: coordinates.Coords) -> list[coordinates.Coords]:
        result = []
        for facing in FACINGS:
            neighbor = position + facing.value
            if neighbor in self.map and self.passable(neighbor):
                result.append(neighbor)
        return result

    def dist(self, s: coordinates.Coords, t: coordinates.Coords) -> int:
        h = lambda x: taxicab_dist(x, t)
        g_score = defaultdict(lambda: inf)
        f_score = defaultdict(lambda: inf)
        g_score[s] = 0
        f_score[s] = h(s)
        open_set = PriorityQueue()
        open_set.put((f_score[s], s))

        while not open_set.empty():
            score, current = open_set.get()
            if current == t:
                break
            if score != f_score[current]:
                continue
            for neighbor in self.neigbors(current):
                tentative_g_score = g_score[current] + 1
                if tentative_g_score < g_score[neighbor]:
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + h(neighbor)
                    open_set.put((f_score[neighbor], neighbor))

        if g_score[t] == inf and len(self.neigbors(t)) > 0:
            return min(g_score[neighbor] for neighbor in self.neigbors(t)) + 1
        return g_score[t]

    @staticmethod
    def simulate_move(
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
    ) -> set[coordinates.Coords]:
        champion = characters.Champion(position, self.arena)
        champion.facing = facing
        champion.weapon = weapon
        return {coordinates.Coords(*position) for position in self.arena.visible_coords(champion)}

    # ==============================================================================================
    # ==============================================================================================

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena: arenas.Arena = arenas.Arena.load(arena_description.name)

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

        # Loot map
        self.loot_map: dict[coordinates.Coords, str] = {}
        self.consumables: set[coordinates.Coords] = set()

        # Visited landmarks i.e. tiles in the map the reveal the unexplored areas
        self.landmarks_visited: dict[coordinates.Coords, bool] = {}

        # Number of steps since we have last seen given tile
        self.last_seen: dict[coordinates.Coords, int] = {}

        # --- Initialize
        for position, tile in self.arena.terrain.items():
            self.map[position] = tile.description()
            self.last_seen[position] = inf

        # --- Compute exploration landmarks
        # Greedy approach, no time to think if this is optimal or hard (NP)
        logger.debug(f"Compute exploration landmarks")
        if arena_description.name in PRECOMPUTED_LANDMARKS:
            self.landmarks_visited = {position: False for position in PRECOMPUTED_LANDMARKS[arena_description.name]}
        else:
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

    def score(self, action: characters.Action, rand: float) -> tuple[float, ...]:
        next_position, next_facing = self.simulate_move(self.position, self.facing, action)

        if not self.passable(next_position):
            return (-inf, -inf, -inf, -inf, -inf, -inf)

        # TODO: Constant value
        ϵ_visibility = 0.4

        # Health gain
        # -----------
        logger.debug("Health gain")
        health_gain = -self.potential_damage[next_position]

        # Damage gain
        # -----------
        logger.debug("Damage gain")
        damage_gain = 0
        if action == characters.Action.ATTACK:
            for cut_position in self.weapon.cut_positions(self.arena.terrain, self.position, self.facing):
                if (
                    cut_position in self.map
                    and self.last_seen[cut_position] == 0
                    and self.map[cut_position].type != "forest"
                    and self.map[cut_position].character
                ):
                    damage_gain += self.weapon.cut_effect().damage

        # Safety gain
        # -----------
        logger.debug("Safety gain")
        safety_gain = 0
        for neighbor in self.neigbors(next_position):
            if self.potential_damage[neighbor] < inf:
                safety_gain -= self.potential_damage[neighbor]
        safety_gain *= self.potential_damage[self.position] <= 0
        safety_gain *= rand < 1 - ϵ_visibility

        # Danger gain
        # -----------
        logger.debug("Danger gain")
        danger_gain = 0
        for cut_position in self.weapon.cut_positions(self.arena.terrain, next_position, next_facing):
            if (
                cut_position in self.map
                and self.last_seen[cut_position] == 0
                and self.map[cut_position].type != "forest"
                and self.map[cut_position].character
            ):
                danger_gain += self.weapon.cut_effect().damage
        danger_gain *= rand < 1 - ϵ_visibility

        # Menhir distance gain
        # --------------------
        logger.debug("Menhir distance gain")
        menhir_gain = -inf
        if self.menhir:
            menhir_gain = self.dist(next_position, self.menhir)
            menhir_gain *= self.potential_damage[self.position] > 0 or menhir_gain > MENHIR_RADIUS
            menhir_gain *= -1

        # Exploration gain
        # ----------------
        logger.debug("Exploration gain")
        exploration_gain = -inf
        if not self.menhir and not all(self.landmarks_visited.values()):
            exploration_gain = inf
            for landmark, visited in self.landmarks_visited.items():
                if not visited:
                    exploration_gain = min(exploration_gain, self.dist(next_position, landmark))
            exploration_gain *= -1
            if exploration_gain > -inf:
                exploration_gain *= rand < 1 - ϵ_visibility

        # Loot gain
        # ---------
        logger.debug("Loot gain")
        loot_gain = -inf
        if len(self.loot_map) > 0 or len(self.consumables) > 0:
            loot_gain = inf
            for position, weapon in self.loot_map.items():
                if WEAPON_ORDER.index(weapon) > WEAPON_ORDER.index(self.weapon.description().name):
                    loot_gain = min(loot_gain, self.dist(next_position, position))
            for position in self.consumables:
                loot_gain = min(loot_gain, self.dist(next_position, position))

            loot_gain *= -1
            if loot_gain > -inf:
                loot_gain *= self.potential_damage[self.position] <= 0
                loot_gain *= rand < 1 - ϵ_visibility

        # Visibility gain
        # ---------------
        logger.debug("Visibility gain")
        visibility_gain = 0
        if action != characters.Action.ATTACK:
            for position in self.visible_coords(next_position, next_facing, self.weapon):
                if self.passable(position) and next_position != position:
                    if self.last_seen[position] / taxicab_dist(next_position, position) < inf:
                        visibility_gain += self.last_seen[position] / taxicab_dist(next_position, position)

        logger.debug(f"Action {action} -> {next_position}, {next_facing}")
        logger.debug(f"Health gain = {health_gain}")
        logger.debug(f"Damage gain = {damage_gain}")
        logger.debug(f"Safety gain = {safety_gain}")
        logger.debug(f"Danger gain = {danger_gain}")
        logger.debug(f"Menhir gain = {menhir_gain}")
        logger.debug(f"Explo. gain = {exploration_gain}")
        logger.debug(f"Loot   gain = {loot_gain}")
        logger.debug(f"Visib. gain = {visibility_gain}")

        return (
            health_gain + damage_gain + 0.5 * (safety_gain + danger_gain),
            loot_gain,
            menhir_gain,
            exploration_gain,
            visibility_gain,
        )

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # try:
        # --- Get visible tiles
        visible_tiles = knowledge.visible_tiles

        # --- Get champion's current attributes
        self.position = knowledge.position
        self.weapon = WEAPONS[visible_tiles[self.position].character.weapon.name]
        self.facing = visible_tiles[self.position].character.facing
        damage_taken = self.health - visible_tiles[self.position].character.health
        self.health = visible_tiles[self.position].character.health

        logger.debug(f"Champion's atrributes")
        logger.debug(f"Position {self.position}")
        logger.debug(f"Facing {self.facing}")
        logger.debug(f"Weapon {self.weapon.description()}")
        logger.debug(f"Health {self.health}")

        # --- Visited landmark?
        # logger.debug(f"Visited landmark?")

        for landmark in self.landmarks_visited:
            if self.dist(self.position, landmark) <= LANDMARK_RADIUS:
                logger.debug(f"Yes, landmark at {landmark}")
                self.landmarks_visited[landmark] = True

        # If all landmarks visited and still no menhir then try again visiting landmarks
        if all(self.landmarks_visited.values()) and not self.menhir:
            logger.debug(f"All landmarks visited, but no Menhir :(")
            for landmark in self.landmarks_visited:
                self.landmarks_visited[landmark] = False

        # --- Update world
        for position, tile in self.map.items():
            if tile.character and self.last_seen[position] > 2:
                self.map[position] = tiles.TileDescription(tile.type, tile.loot, None, tile.consumable, tile.effects)

        for position, tile in visible_tiles.items():
            position = coordinates.Coords(*position)

            # --- Set last-seen-counter to -1 (it gets incremented after this for-loop)
            # logger.debug(f"Set last-seen-counter to -1")
            self.last_seen[position] = -1

            # --- Seen menhir?
            # logger.debug(f"Seen menhir?")
            if tile.type == "menhir":
                logger.debug(f"Yes, menhir at {position}")
                self.menhir = position

            # --- Any loot/consumables?
            if tile.loot and "mist" not in tile.effects and "fire" not in tile.effects:
                self.loot_map[position] = tile.loot.name
            if tile.consumable and "mist" not in tile.effects and "fire" not in tile.effects:
                self.consumables.add(position)

            if (not tile.loot or "mist" in tile.effects or "fire" in tile.effects) and position in self.loot_map:
                del self.loot_map[position]
            if (
                not tile.consumable or "mist" in tile.effects or "fire" in tile.effects
            ) and position in self.consumables:
                self.consumables.remove(position)

            # --- Update map
            # logger.debug(f"Update map")
            if position == self.position:
                tile = tiles.TileDescription(tile.type, tile.loot, None, tile.consumable, tile.effects)

            if enemy := tile.character:
                for replace_position, replace_tile in self.map.items():
                    if replace_tile.character and replace_tile.character.controller_name == enemy.controller_name:
                        self.map[replace_position] = tiles.TileDescription(
                            replace_tile.type,
                            replace_tile.loot,
                            None,
                            replace_tile.consumable,
                            replace_tile.effects,
                        )
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
            # If there is persitent damage at some loot/consumable tile - remove it.
            if position in self.loot_map and self.potential_damage[position] > 0:
                del self.loot_map[position]
            if position in self.consumables and self.potential_damage[position] > 0:
                self.consumables.remove(position)

            if enemy := tile.character:
                # logger.debug(f"Enemy at {position}")
                self.potential_damage[position] = inf
                weapon = WEAPONS[enemy.weapon.name]

                if self.last_seen[position] == 0:
                    for cut_position in weapon.cut_positions(self.arena.terrain, position, enemy.facing):
                        if cut_position in self.map and self.map[cut_position].type != "forest":
                            self.potential_damage[cut_position] += DAMAGE[enemy.weapon.name]
                else:
                    for facing in FACINGS:
                        for cut_position in weapon.cut_positions(self.arena.terrain, position, facing):
                            if cut_position in self.map and self.map[cut_position].type != "forest":
                                self.potential_damage[cut_position] += DAMAGE[enemy.weapon.name] / len(FACINGS)

        if damage_taken > self.potential_damage[self.position]:
            self.potential_damage[self.position] = damage_taken

        actions = ACTIONS.copy()
        if self.weapon.description().name == "amulet":
            actions += [characters.Action.STEP_BACKWARD]

        rand = random.random()
        scores = {action: (*self.score(action, rand), random.random()) for action in actions}
        action = max(scores, key=scores.get)

        # except Exception as e:
        #     # Short circuit in case of failure
        #     logger.debug(f"WARNING!!! Exception {e}")
        #     action = random.choice(RANDOM_ACTIONS)

        return action


POTENTIAL_CONTROLLERS = [
    ReinforcedRogueController("Rogue"),
]
