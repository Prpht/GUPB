import random
import numpy as np

from gupb import controller
from gupb.controller.spejson.dynamic_map_processing import analyze_visible_region, get_state_summary, get_map_derivables
from gupb.controller.spejson.static_map_processing import analyze_map
from gupb.controller.spejson.pathfinding import calculate_dists, proposed_moves_to_keypoints
from gupb.controller.spejson.utils import (
    POSSIBLE_ACTIONS, facing_to_letter, weapons_name_to_letter, get_random_place_on_a_map, move_possible_action_onehot)
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action
from gupb.model.coordinates import Coords


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Spejson(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.position = None
        self.facing = None
        self.health = None
        self.weapon = None
        self.move_number = 0
        self.menhir_found = False
        self.menhir_location = Coords(16, 16)
        self.target = Coords(16, 16)
        self.jitter = 0
        self.weapons_knowledge = None
        self.closest_weapon = None
        self.mist_spotted = False
        self.panic_mode = 0
        self.touched_by_mist = False
        self.clusters = None
        self.adj = None
        self.terrain = None
        self.latest_states = []
        self.map_height = 0
        self.map_width = 0
        self.analytics = {}

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Spejson):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        decision = None
        self.move_number += 1
        self.panic_mode -= 1
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles

        available_actions = POSSIBLE_ACTIONS.copy()

        me = knowledge.visible_tiles[position].character
        self.position = position
        self.facing = me.facing
        self.health = me.health
        self.weapon = me.weapon

        action_type = "FIND_TARGET"

        distances, visited_from = calculate_dists(
            position=(self.position.y, self.position.x),
            facing=facing_to_letter[self.facing],
            traversable=self.analytics['traversable'],
        )

        visibility, menhir_seen, menhir_loc, mist_seen = analyze_visible_region(
            visible_tiles=visible_tiles,
            position=position,
            terrain=self.terrain,
            facing=self.facing,
            weapon=self.weapon,
        )

        if not self.menhir_found and menhir_seen:
            self.menhir_found = True
            self.target = menhir_loc
            self.menhir_location = menhir_loc

        if not self.mist_spotted and mist_seen:
            self.mist_spotted = True
            self.target = self.menhir_location

        if not self.touched_by_mist:
            self.touched_by_mist = (np.sum(visibility['mist_effect'][4:9, 4:9]) > 0)

        someone_in_range = visibility['someone_in_range'][0]

        # Preventing getting stuck
        self.latest_states = (self.latest_states + [(self.position, self.facing)])[-5:]
        if len(self.latest_states) >= 5 and (
                self.latest_states[0] == self.latest_states[1] == self.latest_states[2]
                == self.latest_states[3] == self.latest_states[4]
        ):
            self.panic_mode = 6
            self.target = get_random_place_on_a_map(self.analytics['traversable'])

        # Update weapons knowledge
        to_del = []
        for pos in self.weapons_knowledge:
            pos = Coords(x=pos[1], y=pos[0])
            if pos in visible_tiles:
                loot = visible_tiles[pos].loot
                if loot is None:
                    to_del += [(pos.y, pos.x)]
                else:
                    self.weapons_knowledge[(pos.y, pos.x)] = weapons_name_to_letter[loot.name]

        if (position.y, position.x) in self.weapons_knowledge:
            to_del += [(position.y, position.x)]

        for pos in to_del:
            del self.weapons_knowledge[pos]

        for tile_coord in visible_tiles:
            tile = visible_tiles[tile_coord]
            if (tile_coord[1], tile_coord[0]) not in self.weapons_knowledge and tile.loot is not None \
                    and tile.loot.name != 'knife':
                self.weapons_knowledge[(tile_coord[1], tile_coord[0])] = weapons_name_to_letter[tile.loot.name]

        move_recommendations = proposed_moves_to_keypoints(
            distances=distances,
            visited_from=visited_from,
            menhir_pos=self.target,
            weapons_knowledge=self.weapons_knowledge,
        )

        derivables = get_map_derivables(
            position=position,
            analytics=self.analytics,
            move_recommendations=move_recommendations,
            distances=distances,
        )

        if self.panic_mode <= 0:
            if self.weapon.name == 'knife':
                action_type = "FIND_CLOSEST_WEAPON"
                self.jitter = 0
            else:
                self.target = self.menhir_location
                self.jitter = 0 if self.touched_by_mist else 10

        bad_neighborhood_factor = 0
        if not self.mist_spotted:
            bad_neighborhood_factor = int(np.sum(visibility['someone_here'][3:10, 3:10]) - 1)

        if bad_neighborhood_factor > 2 and self.panic_mode < 2:
            self.panic_mode = 6
            self.target = get_random_place_on_a_map(self.analytics['traversable'])

        # Positions in reach
        if self.weapon.name == "bow_unloaded":
            self.latest_states += ["att"]
            decision = Action.ATTACK
        else:
            if someone_in_range:
                self.latest_states += ["att"]
                decision = Action.ATTACK

        available_actions = [x for x in available_actions if x not in [Action.ATTACK]]

        state = get_state_summary(
            position=position,
            menhir_location=self.menhir_location,
            facing=self.facing,
            hp=self.health,
            weapon=self.weapon,
            epoch=self.move_number,
            menhir_found=self.menhir_found,
            mist_spotted=self.mist_spotted,
            mist_close=self.touched_by_mist,
        )

        all_feature_maps = {
            **visibility,
            **state,
            **derivables,
        }

        if not decision:
            # Rule out stupid moves
            next_block = position + self.facing.value
            if next_block in visible_tiles:
                if visible_tiles[next_block].type in ['sea', 'wall'] or visible_tiles[next_block].character is not None:
                    available_actions = [x for x in available_actions if x not in [Action.STEP_FORWARD]]

            distance_from_target = self.target - position
            distance_from_target = distance_from_target.x ** 2 + distance_from_target.y ** 2

            # Decide on move action
            if distance_from_target < self.jitter and self.target == self.menhir_location and action_type == "FIND_TARGET":
                if Action.STEP_FORWARD in available_actions:
                    if np.random.rand() < 0.7:
                        decision = Action.STEP_FORWARD

                    else:
                        left_ahead = self.target - self.position - self.facing.turn_left().value
                        left_ahead = left_ahead.x ** 2 + left_ahead.y ** 2
                        right_ahead = self.target - self.position - self.facing.turn_right().value
                        right_ahead = right_ahead.x ** 2 + right_ahead.y ** 2

                        if left_ahead < right_ahead:
                            decision = Action.TURN_LEFT if np.random.rand() < 0.7 else Action.TURN_RIGHT
                        else:
                            decision = Action.TURN_RIGHT if np.random.rand() < 0.7 else Action.TURN_LEFT

            else:
                if action_type == "FIND_CLOSEST_WEAPON":
                    move = sorted(
                        [val for key, val in move_recommendations.items() if key != "menhir" and val[0] is not None],
                        key=lambda x: x[1]
                    )[0][0]
                else:
                    move = move_recommendations['menhir'][0]

                if move is None:
                    self.panic_mode = 8
                    self.target = get_random_place_on_a_map(self.analytics['traversable'])
                else:
                    available_actions = (
                        ([move] if move in available_actions else [])
                        + ([Action.ATTACK] if Action.ATTACK in available_actions else [])
                    )

            if not decision and len(available_actions) == 0:
                decision = random.choice([Action.ATTACK, Action.TURN_LEFT])

        if not decision:
            decision = random.choice(available_actions)

        epoch_id = f"{self.first_name}/epoch_{self.move_number}"
        all_feature_maps['decision'] = move_possible_action_onehot[decision]

        return decision

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.position = None
        self.facing = None
        self.health = None
        self.weapon = None
        self.move_number = 0
        self.menhir_found = False
        self.menhir_location = Coords(16, 16)
        self.closest_weapon = None
        self.mist_spotted = False
        self.panic_mode = 0
        self.touched_by_mist = False
        self.latest_states = []

        self.arena_name = arena_description.name
        self.terrain = arenas.Arena.load(self.arena_name).terrain

        self.analytics = analyze_map(self.arena_name)

        self.target = Coords(x=self.analytics['start'][1], y=self.analytics['start'][0])
        self.menhir_location = self.target
        self.clusters = self.analytics['clusters']
        self.adj = self.analytics['adj']
        self.weapons_knowledge = self.analytics['weapons_knowledge']
        self.map_height = self.analytics['height']
        self.map_width = self.analytics['width']

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PINK


POTENTIAL_CONTROLLERS = [
    Spejson("Spejson"),
]
