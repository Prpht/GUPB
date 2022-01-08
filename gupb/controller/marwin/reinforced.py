from collections import defaultdict
import random
import typing

import numpy as np
from sklearn.preprocessing import normalize
from gupb.controller.marwin.deterministic import TURNAROUND_LIMIT

from gupb.model import arenas
from gupb.model import characters
from gupb.model.coordinates import Coords
from gupb.controller.random import POSSIBLE_ACTIONS

from gupb.controller.marwin.base import BaseMarwinController
import gupb.controller.marwin.utils as utils


class ReinforcedMarwin(BaseMarwinController):
	EPS = 0.5
	EPS_DECREASE_RATIO = 0.2
	HEALTH_LOSS_PENALTY_RATIO = -3
	IS_ALIVE_REWARD = 1
	WANDER_MAP = 'wander'
	GO_FOR_WEAPON = 'go_for_weapon'
	CAMP = 'camp'
	PENDING = 'pending_a_new_strategy'
	TURNAROUND_LIMIT = 3
	CLOSE_TO_MENHIR_RADIUS = 10
	CAMPING_LIMIT = 5

	def __init__(self, name):
		super().__init__(name)
		self._strategies = {
			self.WANDER_MAP: self._wander_map,
			self.GO_FOR_WEAPON: self._go_for_weapon,
			self.CAMP: self._camp
		}
		self._round_rewards = {strat: 0 for strat in self._strategies}

		self._turns: typing.Set[Coords] = set()
		self._map_Q = dict()
		self._map_N = dict()
		self._arena = np.zeros(utils.ARENA_SIZE, dtype=int)
		self._arena_description = None
		self._menhir_coords: Coords = None
		self._current_strategy = None
		self._is_pending = True
		self._current_health = characters.CHAMPION_STARTING_HP
		self._current_exploration = self.EPS
		self._current_weapon = None

		self._current_path: typing.List[Coords] = []
		self._current_target_turn: Coords = None
		self._turnaround_index = -1

		self._current_weapon_to_take = None
		self._current_weapon_path: typing.List[Coords] = []

		self._camp_spot_path: typing.List[Coords] = []
		self._is_on_spot = False
		self._camping_rounds = 0
	
	def praise(self, score: int) -> None:
		map_name = self._arena_description.name
		if map_name not in self._map_Q:
			return
		
		for strat in self._strategies:
			n = self._map_N[map_name][strat]
			if n > 0:
				self._map_Q[map_name][strat] += ((self._round_rewards[strat] - self._map_Q[map_name][strat]) / n)
		self._current_exploration -= (self._current_exploration * self.EPS_DECREASE_RATIO)
	
	def die(self) -> None:
		if self._current_strategy is None:
			return
		
		health_lost = self._current_health
		health_loss_penalty = health_lost * self.HEALTH_LOSS_PENALTY_RATIO
		self._round_rewards[self._current_strategy] += health_loss_penalty
	
	def win(self) -> None:
		if self._current_strategy is not None:
			self._round_rewards[self._current_strategy] += self.IS_ALIVE_REWARD
	
	def reset(self, arena_description: arenas.ArenaDescription) -> None:
		self._arena_description = arena_description
		map_name = arena_description.name

		if map_name not in self._map_Q:
			self._map_Q[map_name] = {strat: 0 for strat in self._strategies}
			self._map_N[map_name] = dict()
		
		for strat in self._strategies:
			self._map_N[map_name][strat] = 0
			self._round_rewards[strat] = 0
		
		self._turns.clear()
		self._menhir_coords = None
		self._current_health = characters.CHAMPION_STARTING_HP
		self._current_strategy = None
		self._is_pending = True
		self._arena[:,:] = 0
		self._current_weapon = None

		# WANDER properties
		self._current_path.clear()
		self._current_target_turn = None
		self._turnaround_index = -1

		# GO_FOR_WEAPON properties
		self._current_weapon_to_take = None
		self._current_weapon_path.clear()

		# CAMP properties
		self._camp_spot_path.clear()
		self._is_on_spot = False
		self._camping_rounds = 0
	
	def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
		if self._current_strategy is not None:
			actual_health = self._get_champion(knowledge).health
			if actual_health < self._current_health:
				self._round_rewards[self._current_strategy] += ((self._current_health - actual_health) \
					* self.HEALTH_LOSS_PENALTY_RATIO)
			else:
				self._round_rewards[self._current_strategy] += self.IS_ALIVE_REWARD
			self._current_health = actual_health
		
		if self._is_pending:
			self._current_strategy = self._choose_strategy()
			if self._current_strategy is None:
				return random.choice(POSSIBLE_ACTIONS)
			
			self._is_pending = False
			self._map_N[self._arena_description.name][self._current_strategy] += 1
		return self._strategies[self._current_strategy](knowledge)

# WANDER Strategy	
	def _wander_map(self, knowledge: characters.ChampionKnowledge):
		my_character = self._get_champion(knowledge)
		my_position = knowledge.position
		if self._current_weapon is None:
			self._current_weapon = my_character.weapon.name
		scanned_tiles = utils.scan_terrain(knowledge.visible_tiles, my_character.facing, self._arena, my_position)
		self._update_arena(scanned_tiles)

		current_facing = my_character.facing
		if utils.able_to_attack(scanned_tiles[utils.ENEMY], knowledge.visible_tiles, my_position,\
			current_facing, my_character.weapon):
			return characters.Action.ATTACK
		
		if self._current_target_turn is None:
			# select a random non-mist turn
			if len(self._turns) > 0:
				turns_to_choose = [
					turn for turn in self._turns \
						if (self._arena[turn.y, turn.x] != utils.W_MIST) and turn != my_position
					]
				n_iter = 50
				i = 0
				calculated_path = None
				while calculated_path is None and i < n_iter:
					turn_coords = random.choice(turns_to_choose)
					calculated_path = utils.find_path_to_target(self._arena, my_position, turn_coords) or None
					i += 1
				if calculated_path is None and self._menhir_coords is not None:
					calculated_path = utils.find_path_to_target(self._arena, my_position, self._menhir_coords) or None
				
				if calculated_path is None:
					return random.choice(POSSIBLE_ACTIONS)
				
				self._current_path = calculated_path
				self._current_target_turn = calculated_path[-1]
				self._turnaround_index = 0
			elif -1 < self._turnaround_index < self.TURNAROUND_LIMIT:
				self._turnaround_index += 1
				return characters.Action.TURN_LEFT

		if self._current_target_turn is not None:
			if self._arena[self._current_target_turn.y, self._current_target_turn.x] == utils.W_MIST:
				self._current_target_turn = None
				self._current_path.clear()
				return self._wander_map(knowledge)
			
			if self._current_target_turn == my_position:
				self._is_pending = True  # TODO move at the end of all calculations, don't waste an action
				return characters.Action.STEP_FORWARD  # should never end here
			
			if my_position not in self._current_path:
				self._is_pending = True
				self._current_target_turn = None
				self._current_path.clear()
				return random.choice(POSSIBLE_ACTIONS)
			position_index = self._current_path.index(my_position)
			next_position = self._current_path[position_index + 1]
			next_facing = self._get_next_facing(my_position, next_position)
			if next_facing is None:
				return characters.Action.TURN_LEFT
			else:
				if (my_position + next_facing.value) == self._current_target_turn:
					self._is_pending = True
					self._current_target_turn = None
					self._current_path.clear()
				action = self._get_action_for_facing(my_character.facing, next_facing)
				return action
		
		return random.choice(POSSIBLE_ACTIONS)

# GO FOR WEAPON Strategy
	def _go_for_weapon(self, knowledge: characters.ChampionKnowledge):
		my_character = self._get_champion(knowledge)
		my_position = knowledge.position
		if self._current_weapon is None:
			self._current_weapon = my_character.weapon.name
		scanned_tiles = utils.scan_terrain(knowledge.visible_tiles, my_character.facing, self._arena, my_position)
		self._update_arena(scanned_tiles)

		current_facing = my_character.facing
		if utils.able_to_attack(scanned_tiles[utils.ENEMY], knowledge.visible_tiles, my_position,\
			current_facing, my_character.weapon):
			return characters.Action.ATTACK
		
		if self._current_weapon_to_take is None:
			weapons_to_take = self._get_weapons_to_take(scanned_tiles[utils.WEAPON], my_position)
			if not weapons_to_take:
				return self._fallback_to_wander(knowledge)
			
			weapon_path = None
			for weapon_coords in weapons_to_take:
				weapon_path = utils.find_path_to_target(self._arena, my_position, weapon_coords) or None
				if weapon_path is not None:
					break
			else:
				return self._fallback_to_wander(knowledge)
			self._current_weapon_to_take = weapon_path[-1]
			self._current_weapon_path = weapon_path
		
		if self._current_weapon_to_take is not None:
			if self._arena[self._current_weapon_to_take.y, self._current_weapon_to_take.x] == utils.W_MIST:
				self._current_weapon_to_take = None
				self._current_weapon_path.clear()
				return self._go_for_weapon(knowledge)
			
			if self._current_weapon_to_take == my_position:
				self._is_pending = True  # TODO move at the end of all calculations, don't waste an action
				return characters.Action.STEP_FORWARD  # should never end here
			
			if my_position not in self._current_weapon_path:
				self._is_pending = True
				self._current_weapon_to_take = None
				self._current_weapon_path.clear()
				return random.choice(POSSIBLE_ACTIONS)
			position_index = self._current_weapon_path.index(my_position)
			next_position = self._current_weapon_path[position_index + 1]
			next_facing = self._get_next_facing(my_position, next_position)
			if next_facing is None:
				return characters.Action.TURN_LEFT
			else:
				if (my_position + next_facing.value) == self._current_weapon_to_take:
					self._is_pending = True
					self._current_weapon_to_take = None
					self._current_weapon_path.clear()
				action = self._get_action_for_facing(my_character.facing, next_facing)
				return action
		
		return random.choice(POSSIBLE_ACTIONS)

	
	def _get_weapons_to_take(self, weapons, my_position):
		result = []
		for coords, weapon in weapons:
			if utils.WEAPONS_ORDER[weapon] > utils.WEAPONS_ORDER[self._current_weapon] and\
				self._arena[coords.y, coords.x] != utils.W_MIST:
				result.append(coords)
		if self._menhir_coords is not None:
			return sorted(result, key=lambda x: utils.get_distance(x, self._menhir_coords))
		else:
			return sorted(result, key=lambda x: utils.get_distance(x, my_position))

# CAMP Strategy
	def _camp(self, knowledge: characters.ChampionKnowledge):
		my_character = self._get_champion(knowledge)
		my_position = knowledge.position
		if self._current_weapon is None:
			self._current_weapon = my_character.weapon.name
		scanned_tiles = utils.scan_terrain(knowledge.visible_tiles, my_character.facing, self._arena, my_position)
		self._update_arena(scanned_tiles)

		if self._menhir_coords is None:
			return self._fallback_to_wander(knowledge)
		
		current_facing = my_character.facing
		if utils.able_to_attack(scanned_tiles[utils.ENEMY], knowledge.visible_tiles, my_position,\
			current_facing, my_character.weapon):
			return characters.Action.ATTACK
		
		if not self._camp_spot_path:
			menhir_path = utils.find_path_to_target(self._arena, my_position, self._menhir_coords) or None
			if menhir_path is None:
				return self._fallback_to_wander(knowledge)
		
		if not self._camp_spot_path:
			coords_around_menhir = self._get_coords_around_menhir()
			spot_to_camp = random.choice(coords_around_menhir)
			self._camp_spot_path = utils.find_path_to_target(self._arena, my_position, spot_to_camp)
		
		if self._camp_spot_path:
			position_index = self._camp_spot_path.index(my_position)
			if position_index + 1 == len(self._camp_spot_path):
				self._is_on_spot = True
				self._camping_rounds = 0
				self._camp_spot_path.clear()
			else:
				next_position = self._camp_spot_path[position_index + 1]
				next_facing = self._get_next_facing(my_position, next_position)
				if next_facing is None:
					return characters.Action.TURN_LEFT
				else:
					if (my_position + next_facing.value) == self._camp_spot_path[-1]:
						self._is_on_spot = True
						self._camping_rounds = 0
						self._camp_spot_path.clear()
					action = self._get_action_for_facing(my_character.facing, next_facing)
					return action
		
		if self._is_on_spot:
			turn_action = random.choice([characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT])
			self._camping_rounds += 1
			if self._camping_rounds >= self.CAMPING_LIMIT:
				self._is_on_spot = False
				self._is_pending = True
			return turn_action

		return random.choice(POSSIBLE_ACTIONS)
	
	def _get_coords_around_menhir(self):
		x_start = max(self._menhir_coords.x - self.CLOSE_TO_MENHIR_RADIUS, 0)
		x_end = min(self._menhir_coords.x + self.CLOSE_TO_MENHIR_RADIUS, utils.ARENA_SIZE[0])
		y_start = max(self._menhir_coords.y - self.CLOSE_TO_MENHIR_RADIUS, 0)
		y_end = min(self._menhir_coords.y + self.CLOSE_TO_MENHIR_RADIUS, utils.ARENA_SIZE[1])

		result = []
		for x in range(x_start, x_end):
			for y in range(y_start, y_end):
				if self._arena[y, x] == utils.W_PASSAGE:
					result.append(Coords(x=x, y=y))
		return result

# REST
	def _fallback_to_wander(self, knowledge: characters.ChampionKnowledge):
		self._map_N[self._arena_description.name][self._current_strategy] -= 1
		self._current_strategy = self.WANDER_MAP
		return self._wander_map(knowledge)

	def _update_arena(self, scanned_tiles):
		if scanned_tiles[utils.MENHIR]:
			self._menhir_coords = scanned_tiles[utils.MENHIR][0]
			self._arena[self._menhir_coords[1], self._menhir_coords[0]] = utils.W_PASSAGE
		
		for coords in scanned_tiles[utils.PASSAGE]:
			self._arena[coords[1], coords[0]] = utils.W_PASSAGE
        
		for unpassable in scanned_tiles[utils.SEA] + scanned_tiles[utils.WALL]:
			self._arena[unpassable[1], unpassable[0]] = utils.W_BLOCKERS
        
		for coords, weapon in scanned_tiles[utils.WEAPON]:
			if utils.WEAPONS_ORDER[weapon] < utils.WEAPONS_ORDER[self._current_weapon]:
				self._arena[coords[1], coords[0]] = utils.W_TAKEN_WEAPON
			else:
				self._arena[coords[1], coords[0]] = utils.W_PASSAGE
		
		if self._menhir_coords is not None:
			all_turns = self._turns.union(scanned_tiles[utils.TURN])
			turns_close_to_menhir = [turn for turn in all_turns \
				if abs(utils.get_distance(self._menhir_coords, turn)) <= self.CLOSE_TO_MENHIR_RADIUS]
			self._turns.clear()
			self._turns.update(turns_close_to_menhir)
		else:
			self._turns.clear()
			self._turns.update(scanned_tiles[utils.TURN])
		
		for mist in scanned_tiles[utils.MIST]:
			self._arena[mist[1], mist[0]] = utils.W_MIST
	
	@staticmethod
	def _get_next_facing(current_position: Coords, next_position: Coords) -> characters.Facing:
		facings = [characters.Facing.LEFT, characters.Facing.RIGHT, characters.Facing.UP, characters.Facing.DOWN]
		for facing in facings:
			if (current_position + facing.value) == next_position:
				return facing
		return None
	
	@staticmethod
	def _get_action_for_facing(current_facing: characters.Facing, next_facing: characters.Facing) -> characters.Action:
		if current_facing == next_facing:
			return characters.Action.STEP_FORWARD
		elif current_facing.turn_right() == next_facing:
			return characters.Action.TURN_RIGHT
		return characters.Action.TURN_LEFT
	
	def _choose_strategy(self):
		if self._arena_description is None or self._arena_description.name not in self._map_Q:
			return None
		q_table = self._map_Q[self._arena_description.name]
		values = []
		strategies = []
		for strat, val in q_table.items():
			values.append(val)
			strategies.append(strat)
		if random.random() < self._current_exploration or np.sum(values) == 0:
			strategy = random.choice(strategies)
		else:
			# max_mask = (np.array(values) == np.max(values)).astype(float)
			# probs = normalize(max_mask.reshape(1, -1), norm='l1')[0]
			probs = normalize(np.array(values).reshape(1, -1), norm='l1')[0]
			strategy = np.random.choice(strategies, p=np.abs(probs))
		return strategy


POTENTIAL_CONTROLLERS = [
	ReinforcedMarwin("Marwin")
]

