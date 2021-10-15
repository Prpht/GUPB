import math

from gupb.model import arenas
from gupb.model import characters
from typing import NamedTuple, Optional, Dict

class EvaderController:

	def __init__(self, first_name: str):
		self.first_name: str = first_name

	def __eq__(self, other: object) -> bool:
		if isinstance(other, EvaderController):
			return True
		return False

	def __hash__(self) -> int:
		return 99

	def reset(self, arena_description: arenas.ArenaDescription) -> None:
		pass

	def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
		enemies_facing_our_way = self.scan_for_enemies(knowledge)
		if enemies_facing_our_way:
			nearest_enemy = self.calc_distance(enemies_facing_our_way)
			if nearest_enemy <= 2.0:
				action = characters.Action.STEP_FORWARD
			else:
				action = characters.Action.TURN_LEFT

		else: action = characters.Action.DO_NOTHING
		return action  # DO_NOTHING



	def scan_for_enemies(self, knowledge: characters.ChampionKnowledge) -> Optional[NamedTuple]:
		tiles_in_sight = knowledge.visible_tiles
		my_position = knowledge.position
		my_character = knowledge.visible_tiles[my_position].character
		enemies_facing_our_way = []
		for tile, tile_desc in tiles_in_sight.items():
			if tile_desc.character:  ## enemy in sight
				if tile_desc.character.facing == (-my_character.facing):
					enemies_facing_our_way.append(tile)

		return None if not enemies_facing_our_way else enemies_facing_our_way


	def calc_distance(self, enemies) -> float:
		nearest = math.inf
		for position in enemies:
			distance = math.sqrt(pow(position["x"],2) + pow(position["y"],2))
			if distance  < nearest:
				nearest = distance
		return nearest

	@property
	def name(self) -> str:
		return f'RandomController{self.first_name}'

	@property
	def preferred_tabard(self) -> characters.Tabard:
		return characters.Tabard.VIOLET