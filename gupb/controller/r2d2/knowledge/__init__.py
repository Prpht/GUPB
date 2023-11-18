from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import numpy as np
from gupb.controller.r2d2.utils import LARGEST_ARENA_SHAPE, tiles_mapping
from gupb.model.arenas import Arena

from gupb.model.characters import ChampionKnowledge


@dataclass(frozen=True)
class R2D2Knowledge:
    chempion_knowledge: ChampionKnowledge
    world_state: WorldState 
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
        matrix_walkable = self.matrix[:self.arena_shape[0], :self.arena_shape[1]]
        matrix_walkable = np.logical_and(matrix_walkable != tiles_mapping["sea"], matrix_walkable != tiles_mapping["wall"])
        matrix_walkable = np.logical_and(matrix_walkable, matrix_walkable != tiles_mapping["enymy"])
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
    



