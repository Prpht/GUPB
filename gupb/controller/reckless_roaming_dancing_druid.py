import numpy as np
from statemachine import StateMachine, State
from pathfinding.finder.bi_a_star import BiAStarFinder
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords



LARGEST_ARENA_SHAPE = (100, 100)

# Non walking tiles are: [0, 2, 3]
tiles_mapping = {
    "out": 0,
    "land": 1,
    "sea": 2,
    "wall": 3,
    "menhir": 4,
    "champion": 5,
    "knife": 6,
    "sword": 7,
    "bow_unloaded": 8,
    "bow_loaded": 8, # "bow_unloaded" and "bow_loaded" are the same tile
    "axe": 9,
    "amulet": 10,
    "potion": 11,
    "enymy": 12,
    "mist": 13,
}

update_facing_right = {
    characters.Facing.UP: characters.Facing.RIGHT,
    characters.Facing.RIGHT: characters.Facing.DOWN,
    characters.Facing.DOWN: characters.Facing.LEFT,
    characters.Facing.LEFT: characters.Facing.UP,
}

update_facing_left = {
    characters.Facing.UP: characters.Facing.LEFT,
    characters.Facing.RIGHT: characters.Facing.UP,
    characters.Facing.DOWN: characters.Facing.RIGHT,
    characters.Facing.LEFT: characters.Facing.DOWN,
}

class R2D2StateMachine(StateMachine):

    # Define StateMachine states
    searching_for_menhir = State('SearchingForMenhir', value="SearchingForMenhir", initial=True)
    approaching_menhir = State('ApproachingMenhir', value="ApproachingMenhir")
    defending = State('Defending', value="Defending")
    defending_turn = State('DefendingTurn', value="Defending")
    defending_attack = State('DefendingAttack', value="Defending")

    # Define the transitions of the StateMachine
    approach_menhir = searching_for_menhir.to(approaching_menhir)
    defend = \
        approaching_menhir.to(defending) | \
        defending.to(defending_attack) | \
        defending_attack.to(defending_turn) | \
        defending_turn.to(defending_attack)


class RecklessRoamingDancingDruid(controller.Controller):

    def action_turn_left(self):
        self.facing = update_facing_left[self.facing]
        return characters.Action.TURN_LEFT

    def action_turn_right(self):
        self.facing = update_facing_right[self.facing]
        return characters.Action.TURN_RIGHT
    
    def action_step_forward(self):
        return characters.Action.STEP_FORWARD
    
    def action_attack(self):
        return characters.Action.ATTACK
    
    def action_do_nothing(self):
        return characters.Action.DO_NOTHING

    def _init_matrix(self, arena: Arena):
        self.arena_shape = arena.size[1], arena.size[0]
        for coords, tile in arena.terrain.items():
            self.matrix[coords[1], coords[0]] = tiles_mapping[tile.description().type]

        # Save the initial state of the arena for decay mechanism
        self.initial_arena = self.matrix.copy()

        # Create a walkable matrix for pathfinding
        matrix_walkable = self.matrix[:self.arena_shape[0], :self.arena_shape[1]]
        matrix_walkable = np.logical_and(matrix_walkable != 2, matrix_walkable != 3)
        self.matrix_walkable = matrix_walkable.astype(int)
    
    def _fill_matrix(self, champion_knowledge: ChampionKnowledge):
        
        # Update Visible tiles
        for coords, tile_description in champion_knowledge.visible_tiles.items():

            if tile_description.type == "menhir":
                self.matrix[coords[1], coords[0]] = tiles_mapping[tile_description.type]
                self.menhir_position = coords
                if self.state_machine.current_state == self.state_machine.searching_for_menhir:
                    self.state_machine.approach_menhir()
            
            if tile_description.loot:
                self.matrix[coords[1], coords[0]] = tiles_mapping[tile_description.loot.name]
            
            if tile_description.consumable:
                self.matrix[coords[1], coords[0]] = tiles_mapping[tile_description.consumable.name]
            
            if tile_description.character:
                self.matrix[coords[1], coords[0]] = tiles_mapping["enymy"]
            
            if tile_description.effects:
                if "mist" in tile_description.effects:
                    self.matrix[coords[1], coords[0]] = tiles_mapping["mist"]

        # Update Champion position
        self.matrix[champion_knowledge.position.y, champion_knowledge.position.x] = tiles_mapping["champion"]
        self.champion_position = champion_knowledge.position
    
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
            self.decay_mask[coords[1], coords[0]] = self.decay

    def __init__(self, first_name: str, decay: int = 1):
        self.first_name: str = first_name

        # Controls the memory of the agent. Decay of n, means that the agent will assume that
        # the item is still there for n steps, even when it's not visible. Note that the decay
        # of 1 means no memory at all, the higher the decay, the longer the memory.
        # TODO Could we use a different decay for dynamic characters and a different one for static items?
        self.decay = decay
        self.decay_mask = np.zeros(LARGEST_ARENA_SHAPE, np.int8)

        # Define a state machine to manage the agent's behaviour
        self.state_machine = R2D2StateMachine()

        self.arena_id = None
        self.arena_shape = None
        self.initial_arena = None
        self.menhir_position = None
        self.champion_position = None
        self.initial_facing = None
        self.facing = None
        self.finder = BiAStarFinder(diagonal_movement=DiagonalMovement.never)

        # This is the representation of the map state that will be returned as the observation
        self.matrix = np.zeros(LARGEST_ARENA_SHAPE, dtype=np.int8)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RecklessRoamingDancingDruid):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)
    
    def _move_to(self, target_coords: Coords, knowledge: characters.ChampionKnowledge) -> characters.Action:
        
        # If already in 
        if self.champion_position == target_coords:
            return self.action_do_nothing()
        
        # Find a path to the target
        # - Translate the matrix into an appropriate format for the pathfinding algorithm
        grid = Grid(matrix=self.matrix_walkable)
        start = grid.node(*self.champion_position)
        end = grid.node(*target_coords)

        # - Find the path
        path, _ = self.finder.find_path(start, end, grid)
        next_tile_coords = Coords(path[1].x, path[1].y)

        # - Move to the next tile
        delta = next_tile_coords - self.champion_position
        facing = knowledge.visible_tiles[self.champion_position].character.facing

        if facing == characters.Facing.UP:
            if delta == characters.Facing.UP:
                return self.action_step_forward()
            if delta == characters.Facing.LEFT:
                return self.action_turn_left()
            return self.action_turn_right()
        
        if facing == characters.Facing.RIGHT:
            if delta == characters.Facing.RIGHT:
                return self.action_step_forward()
            if delta == characters.Facing.UP:
                return self.action_turn_left()
            return self.action_turn_right()
        
        if facing == characters.Facing.DOWN:
            if delta == characters.Facing.DOWN:
                return self.action_step_forward()
            if delta == characters.Facing.RIGHT:
                return self.action_turn_left()
            return self.action_turn_right()
        
        if facing == characters.Facing.LEFT:
            if delta == characters.Facing.LEFT:
                return self.action_step_forward()
            if delta == characters.Facing.DOWN:
                return self.action_turn_left()
            return self.action_turn_right()

    def _searching_for_menhir(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.action_turn_right()
    
    def _approaching_menhir(self, knowledge: characters.ChampionKnowledge, eps = 0) -> characters.Action:
        
        delta = self.champion_position - self.menhir_position
        delta = abs(delta[0]) + abs(delta[1])
        if delta <= eps:
            self.state_machine.defend()
            return self._defending(knowledge)
        
        return self._move_to(self.menhir_position, knowledge)

    def _defending(self, knowledge: characters.ChampionKnowledge) -> characters.Action:

        self.state_machine.defend()
        if self.state_machine.current_state == self.state_machine.defending_attack:
            return self.action_attack()
        if self.state_machine.current_state == self.state_machine.defending_turn:
            return self.action_turn_right()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        
        # Apply decay and update the decay mask
        self._decay_step(knowledge)
        
        # Update the matrix with the current observation
        self._fill_matrix(knowledge)

        # Save the facing of the champion on the first observation
        if not self.facing:
            self.facing = knowledge.visible_tiles[self.champion_position].character.facing
        
        # Act according to the current state
        if self.state_machine.current_state.value == self.state_machine.searching_for_menhir.value:
            return self._searching_for_menhir(knowledge)
        
        if self.state_machine.current_state.value == self.state_machine.approaching_menhir.value:
            action = self._approaching_menhir(knowledge)
            return action
        
        if self.state_machine.current_state.value == self.state_machine.defending.value:
            return self._defending(knowledge)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.arena_id = arena_description.name
        self._init_matrix(Arena.load(self.arena_id))

    @property
    def name(self) -> str:
        return f'RecklessRoamingDancingDruid_{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.R2D2
