from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import numpy as np
from gupb.controller.r2d2.utils import LARGEST_ARENA_SHAPE, tiles_mapping
from gupb.model.arenas import Arena

from gupb.model.characters import ChampionDescription, ChampionKnowledge
from gupb.model.coordinates import Coords
from gupb.model.tiles import TileDescription
from gupb.model.weapons import Knife, Sword, Axe, Bow, Amulet


@dataclass(frozen=True)
class R2D2Knowledge:
    champion_knowledge: ChampionKnowledge
    world_state: WorldState 
    arena: Arena
    current_weapon: str


class WorldState:
    def __init__(self, arena: Arena, decay: int = 5):
        self.step_counter = 0
        self.matrix = np.zeros(LARGEST_ARENA_SHAPE, dtype=np.int8)
        self.arena_shape = arena.size[1], arena.size[0]
        for coords, tile in arena.terrain.items():
            self.matrix[coords[1], coords[0]] = tiles_mapping[tile.description().type]

        # Save the initial state of the arena for decay mechanism
        self.initial_arena = self.matrix.copy()

        # Define the exploration matrix wich stores explored tiles
        self.explored = self.initial_arena.copy()[:self.arena_shape[0], :self.arena_shape[1]]
        self.explored = np.logical_or(self.explored == tiles_mapping["sea"], self.explored != tiles_mapping["wall"])

        # Define the decay mask
        self.decay = decay
        self.decay_mask = np.zeros(LARGEST_ARENA_SHAPE, np.int8)

        self.menhir_position = None
        self.mist_present = False

    def update(self, knowledge: ChampionKnowledge):
        # Apply decay and update the decay mask
        self._decay_step(knowledge)
        
        # Update the matrix with the current observation
        self._fill_matrix(knowledge)

        # Update the explored matrix
        self.update_explored(knowledge)

        # Update the state of the agent
        self._update_state(knowledge)

        self.step_counter += 1

    def _decay_step(self, champion_knowledge: ChampionKnowledge):
        
        # Decay the whole mask
        self.decay_mask = np.maximum(self.decay_mask - 1, 0)

        # Reset decayed tiles
        self.matrix = np.where(self.decay_mask == 0, self.initial_arena, self.matrix)
        # - but keep the menhir in place once discovered
        if self.menhir_position:
            self.matrix[self.menhir_position[1], self.menhir_position[0]] = tiles_mapping["menhir"]

        # Reset decay of visible tiles
        for coords, tile_description in champion_knowledge.visible_tiles.items():
            if tile_description.character:
                # - if the tile is occupied by an enemy, reset the decay to 0, we need live information
                self.decay_mask[coords[1], coords[0]] = 0
            else:
                # - otherwise, reset the decay to the initial value
                self.decay_mask[coords[1], coords[0]] = self.decay
    
    def _update_state(self, champion_knowledge: ChampionKnowledge):
        # Update Champion position
        self.matrix[champion_knowledge.position.y, champion_knowledge.position.x] = tiles_mapping["champion"]

        # Create a walkable matrix for pathfinding
        matrix_walkable = self.matrix[:self.arena_shape[0], :self.arena_shape[1]].copy()
        matrix_walkable[matrix_walkable == tiles_mapping["sea"]] = 0
        matrix_walkable[matrix_walkable == tiles_mapping["wall"]] = 0
        matrix_walkable[matrix_walkable == tiles_mapping["enymy"]] = 0
        matrix_walkable[matrix_walkable > 0] = 1
        self.matrix_walkable = matrix_walkable.astype(int)

    def _fill_matrix(self, champion_knowledge: ChampionKnowledge):
        
        # Update Visible tiles
        for coords, tile_description in champion_knowledge.visible_tiles.items():

            if tile_description.type == "menhir":
                self.matrix[coords[1], coords[0]] = tiles_mapping[tile_description.type]
                self.menhir_position = coords
            
            if tile_description.loot:
                self.matrix[coords[1], coords[0]] = tiles_mapping[tile_description.loot.name]
            
            if tile_description.consumable:
                self.matrix[coords[1], coords[0]] = tiles_mapping[tile_description.consumable.name]
            
            if tile_description.character:
                self.matrix[coords[1], coords[0]] = tiles_mapping["enymy"]
            
            if tile_description.effects:
                if "mist" in tile_description.effects:
                    self.matrix[coords[1], coords[0]] = tiles_mapping["mist"]
                    self.mist_present = True


    def update_explored(self, champion_knowledge: ChampionKnowledge):
        # Update the explored matrix
        for coords, tile_description in champion_knowledge.visible_tiles.items():
            self.explored[coords[1], coords[0]] = True


def get_threating_enemies_map(knowledge: R2D2Knowledge) -> list[tuple[Coords, ChampionDescription]]:
    """
    Get a map of enemies that are a threat to the agent.
    """
    threating_enemies = []
    my_coords = knowledge.champion_knowledge.position
    for coords, tile_description in knowledge.champion_knowledge.visible_tiles.items():
        if tile_description.character:
            my_description = knowledge.champion_knowledge.visible_tiles[my_coords].character
            if is_enemy_a_threat(my_coords, coords, my_description, tile_description.character, knowledge):
                threating_enemies.append((coords, tile_description.character))
    return threating_enemies
    
def is_enemy_a_threat(my_coords, enemy_coords, me: ChampionDescription, enemy: ChampionDescription, knowledge: R2D2Knowledge) -> bool:
    """
    Check if the enemy is a threat to the agent.
    """
    in_range = my_coords in get_cut_positions(enemy_coords, enemy, knowledge)
    enemy_in_range = enemy_coords in get_cut_positions(my_coords, me, knowledge)
    return (enemy.health > me.health) 


def get_cut_positions(coords: Coords, character: ChampionDescription, knowledge: R2D2Knowledge) -> list[Coords]:
    if not isinstance(coords, Coords):
        coords = Coords(coords[0], coords[1])
    weapon_class = {
        "knife": Knife,
        "sword": Sword,
        "axe": Axe,
        "bow": Bow,
        "bow_loaded": Bow,
        "bow_unloaded": Bow,
        "amulet": Amulet
    }[character.weapon.name]
    cut_positions = weapon_class.cut_positions(
        knowledge.arena.terrain,
        coords,
        character.facing
    )
    return cut_positions

def get_enemies_in_cut_range(knowledge: R2D2Knowledge) -> list[tuple[Coords, ChampionDescription]]:
    """
    Get a map of enemies that are in the range of the agent's weapon.
    """
    enemies_in_range = []
    coords = knowledge.champion_knowledge.position
    my_description = knowledge.champion_knowledge.visible_tiles[coords].character
    for coords in get_cut_positions(coords, my_description, knowledge):
        if coords == knowledge.champion_knowledge.position:
            continue
        if (enymy := knowledge.champion_knowledge.visible_tiles.get(coords, None)):
            if enymy.character:
                enemies_in_range.append((coords, enymy.character))
    return enemies_in_range

def decide_whether_attack(knowledge: R2D2Knowledge):
    enemies_in_range = get_enemies_in_cut_range(knowledge)
    my_description = knowledge.champion_knowledge.visible_tiles[knowledge.champion_knowledge.position].character
    if len(enemies_in_range) == 0:
        return False
    enemies_cut_ranges = set()
    for coords, enemy in enemies_in_range:
        cuts = get_cut_positions(coords, enemy, knowledge)
        enemies_cut_ranges.update(set((y, x) for y, x in cuts))
    in_enemies_cut_range = knowledge.champion_knowledge.position in enemies_cut_ranges
    
    all_weaker = all([enemy.health <= my_description.health for _, enemy in enemies_in_range])
    return all_weaker or (enemies_in_range and not in_enemies_cut_range)

def get_all_enemies(knowledge: R2D2Knowledge) -> list[tuple[Coords, ChampionDescription]]:
    """
    Get a map of all enemies.
    """
    all_enemies = []
    for coords, tile_description in knowledge.champion_knowledge.visible_tiles.items():
        if coords == knowledge.champion_knowledge.position:
            continue
        if tile_description.character:
            all_enemies.append((coords, tile_description.character))
    return all_enemies