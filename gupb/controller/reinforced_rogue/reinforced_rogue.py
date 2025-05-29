import random
import logging

from math import inf
from typing import Optional

from gupb import controller
from gupb.model import arenas
from gupb.model import weapons
from gupb.model import characters
from gupb.model import coordinates

from .map import Map
from .constants import *
from .utils import simulate_action, manhattan_dist

logger = logging.getLogger("verbose")


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class ReinforcedRogueController(controller.Controller):
    def __init__(self, first_name: str = ""):
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

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.map: Map = Map(arena_description)

        # Champion's attributes
        self.position: Optional[coordinates.Coords] = None
        self.facing: Optional[characters.Facing] = None
        self.weapon: Optional[weapons.WeaponDescription] = None
        self.health: int = characters.CHAMPION_STARTING_HP

    def score(self, action: characters.Action, rand: float) -> tuple[float, ...]:
        next_position, next_facing = simulate_action(self.position, self.facing, action)
        next_tile = self.map.tiles[next_position]

        if not self.map.is_passable(next_position):
            return (-inf,)

        # Health gain
        # -----------
        health_gain = 0
        health_gain -= DAMAGE_DICT[next_tile.consumable.name] if next_tile.consumable else 0
        health_gain -= sum(DAMAGE_DICT[effect.type] for effect in next_tile.effects)

        for enemy_position, enemy in self.map.get_enemies().items():
            cut_positions = self.map.get_cut_positions(enemy.weapon, enemy_position, enemy.facing)
            if (
                self.map.last_seen[enemy_position] == 0
                and next_position in cut_positions
                and self.map.tiles[next_position].type != "forest"
            ):
                health_gain -= DAMAGE_DICT[enemy.weapon.name]

            # TODO
            if self.map.last_seen[enemy_position] > 0:
                for facing in characters.Facing:
                    cut_positions = self.map.get_cut_positions(enemy.weapon, enemy_position, facing)
                    if next_position in cut_positions and self.map.tiles[next_position].type != "forest":
                        health_gain -= 1 / len(characters.Facing) * DAMAGE_DICT[enemy.weapon.name]

        if next_position == self.position and self.damage_registered > -health_gain:
            health_gain = -self.damage_registered

        health_gain /= self.health

        # Damage gain
        # -----------
        damage_gain = 0
        if action == characters.Action.ATTACK:
            cut_positions = self.map.get_cut_positions(self.weapon, self.position, self.facing)
            for enemy_position, enemy in self.map.get_enemies().items():
                if (
                    self.map.last_seen[enemy_position] == 0
                    and enemy_position in cut_positions
                    and self.map.tiles[enemy_position].type != "forest"
                ):
                    damage_gain += DAMAGE_DICT[self.weapon.name] / enemy.health

        # Safety gain
        # -----------
        safety_gain = 0
        for adj in self.map.get_adjacent(next_position):
            tile = self.map.tiles[adj]

            safety_gain -= DAMAGE_DICT[tile.consumable.name] if tile.consumable else 0
            safety_gain -= sum(DAMAGE_DICT[effect.type] for effect in tile.effects)

            for enemy_position, enemy in self.map.get_enemies().items():
                cut_positions = self.map.get_cut_positions(enemy.weapon, enemy_position, enemy.facing)
                if self.map.last_seen[enemy_position] == 0 and adj in cut_positions and tile.type != "forest":
                    safety_gain -= DAMAGE_DICT[enemy.weapon.name]

        safety_gain *= health_gain >= 0
        safety_gain /= self.health

        # Danger gain
        # -----------
        danger_gain = 0
        cut_positions = self.map.get_cut_positions(self.weapon, next_position, next_facing)
        for enemy_position, enemy in self.map.get_enemies().items():
            if (
                self.map.last_seen[enemy_position] == 0
                and enemy_position in cut_positions
                and self.map.tiles[enemy_position].type != "forest"
            ):
                danger_gain += DAMAGE_DICT[self.weapon.name] / enemy.health

        # Distance gain
        # -------------
        dist_loot = self.map.get_min_dist_loot(next_position, self.weapon)
        dist_prey = self.map.get_min_dist_prey(next_position, self.health, self.weapon)
        dist_menhir = self.map.get_min_dist_menhir(next_position)
        dist_landmark = self.map.get_min_dist_landmark(next_position)

        if self.map.menhir and dist_menhir < MENHIR_RADIUS and health_gain >= 0:
            dist_menhir = inf

        if self.map.menhir and health_gain < 0:
            dist_loot = inf
            dist_prey = inf

        dist_gain = -min(dist_loot, dist_prey, dist_menhir, dist_landmark)

        # Visibility gain
        # ---------------
        visibility_gain = 0
        if action != characters.Action.ATTACK:
            for visible in self.map.get_visible_coords(next_position, next_facing, self.weapon):
                if next_position != visible:
                    visibility_gain += self.map.last_seen[visible] / manhattan_dist(next_position, visible)

        # Compute score
        # -------------
        if rand < EPSILON and effects.EffectDescription("mist") not in self.map.tiles[self.position].effects:
            return (health_gain + damage_gain, visibility_gain, dist_gain)

        if effects.EffectDescription("mist") in self.map.tiles[self.position].effects:
            return (health_gain + damage_gain, dist_gain, visibility_gain)

        return (health_gain + damage_gain + GAMMA * (safety_gain + danger_gain), dist_gain, visibility_gain)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            visible_tiles = knowledge.visible_tiles

            self.position = knowledge.position
            self.damage_registered = self.health - visible_tiles[self.position].character.health

            self.health = visible_tiles[self.position].character.health
            self.weapon = visible_tiles[self.position].character.weapon
            self.facing = visible_tiles[self.position].character.facing

            if self.weapon.name == "bow_unloaded":
                self.weapon = weapons.WeaponDescription("bow_loaded")

            self.map.update(self.position, visible_tiles)

            actions = POSSIBLE_ACTIONS.copy()
            actions += [characters.Action.STEP_BACKWARD] if self.weapon.name == "amulet" else []

            rand = random.random()
            scores = {action: (*self.score(action, rand), random.random()) for action in actions}
            return max(scores, key=scores.get)

        except Exception as e:
            logger.warning(f"Exception {e}")
            return random.choice(RANDOM_ACTIONS)
