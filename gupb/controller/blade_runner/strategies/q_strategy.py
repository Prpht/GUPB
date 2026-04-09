# logic based on page 131 of "Reinforcement Learning: An Introduction"

import random
from collections import defaultdict
from typing import Optional

from .strategy_api import Strategy
from gupb.model import characters, arenas
from gupb.model.coordinates import Coords


class QStrategy(Strategy):
    def __init__(self) -> None:
        self.alpha = 0.25
        self.gamma = 0.95
        self.epsilon = 0.20

        self.q_table: dict[tuple[tuple, characters.Action], float] = defaultdict(float) # Q(state, action) -> value; Q[((1,0,1,0,0,1), STEP_FORWARD)] = 0.73

        self.last_state: Optional[tuple] = None
        self.last_action: Optional[characters.Action] = None
        self.last_position: Optional[Coords] = None

        self.visited: set[Coords] = set()

        self.menhir_position: Optional[Coords] = None

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.last_state = None
        self.last_action = None
        self.last_position = None
        self.visited = set()
        self.menhir_position = None

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:

        current_position = knowledge.position
        current_state = self._build_state(knowledge)

        if self.menhir_position is None and self._find_menhir(knowledge) is not None:
            self.menhir_position = self._find_menhir(knowledge)

        reward = self._compute_step_reward(
            knowledge=knowledge,
            previous_position=self.last_position,
            current_position=current_position,
            previous_action=self.last_action,
        )

        if self.last_state is not None and self.last_action is not None:
            self._update_q(
                prev_state=self.last_state,
                prev_action=self.last_action,
                reward=reward,
                next_state=current_state,
            )

        action = self._choose_action(current_state)

        self.last_state = current_state
        self.last_action = action
        self.last_position = current_position
        self.visited.add(current_position)

        return action

    def praise(self, score: int) -> None:
        if self.last_state is not None and self.last_action is not None:
            old_q = self._get_q(self.last_state, self.last_action)
            final_reward = float(score)
            new_q = old_q + self.alpha * (final_reward - old_q)
            self.q_table[(self.last_state, self.last_action)] = new_q

    def _build_state(self, knowledge: characters.ChampionKnowledge) -> tuple:
        position = knowledge.position
        facing = self._get_my_facing(knowledge)

        front_coords = self._get_front_coords(position, facing)
        front_tile = self._get_tile(knowledge, front_coords)

        blocked_front = int(self._is_blocked(front_tile))
        enemy_in_front = int(self._enemy_ahead(knowledge))
        enemy_visible = int(self._enemy_visible(knowledge))
        loot_visible = int(self._loot_visible(knowledge))
        consumable_visible = int(self._consumable_visible(knowledge))
        repeated_position = int(position in self.visited)

        return (
            blocked_front,
            enemy_in_front,
            enemy_visible,
            loot_visible,
            consumable_visible,
            repeated_position,
        )

    def _available_actions(self) -> list[characters.Action]:
        return [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
            characters.Action.ATTACK,
            #characters.Action.STEP_LEFT, caused worse results, maybe the state is too simple
            #characters.Action.STEP_RIGHT,
            #characters.Action.STEP_BACKWARD,
            #characters.Action.DO_NOTHING,
        ]

    def _choose_action(self, state: tuple) -> characters.Action:
        actions = self._available_actions()

        if random.random() < self.epsilon:
            return random.choice(actions)

        best_value = max(self._get_q(state, action) for action in actions)
        best_actions = [a for a in actions if self._get_q(state, a) == best_value]
        return random.choice(best_actions)

    def _update_q(
        self,
        prev_state: tuple,
        prev_action: characters.Action,
        reward: float,
        next_state: tuple,
    ) -> None:
        old_q = self._get_q(prev_state, prev_action)
        max_next_q = max(self._get_q(next_state, action) for action in self._available_actions())
        new_q = old_q + self.alpha * (reward + self.gamma * max_next_q - old_q) # page 131
        self.q_table[(prev_state, prev_action)] = new_q

    def _get_q(self, state: tuple, action: characters.Action) -> float:
        return self.q_table[(state, action)]

    def _compute_step_reward(
        self,
        knowledge: characters.ChampionKnowledge,
        previous_position: Optional[Coords],
        current_position: Coords,
        previous_action: Optional[characters.Action],
    ) -> float:
        if previous_position is None:
            return 0.0

        reward = -0.05

        if current_position == previous_position:
            reward -= 0.4
        else:
            reward += 0.1

        if previous_action == characters.Action.ATTACK:
            if self._enemy_ahead(knowledge):
                reward += 0.4
            else:
                reward -= 0.2

        if current_position in self.visited:
            reward -= 0.1

        return reward

    def _get_my_facing(self, knowledge: characters.ChampionKnowledge):
        my_tile = knowledge.visible_tiles[knowledge.position]
        return my_tile.character.facing

    def _facing_to_vector(self, facing) -> Coords:
        if facing == characters.Facing.UP:
            return Coords(0, -1)
        if facing == characters.Facing.DOWN:
            return Coords(0, 1)
        if facing == characters.Facing.LEFT:
            return Coords(-1, 0)
        return Coords(1, 0)

    def _get_front_coords(self, position: Coords, facing) -> Coords:
        return position + self._facing_to_vector(facing)

    def _get_tile(self, knowledge: characters.ChampionKnowledge, coords: Coords):
        return knowledge.visible_tiles.get(coords)

    def _is_blocked(self, tile) -> bool:
        if tile is None:
            return True
        return tile.type in {"wall", "sea"}

    def _enemy_ahead(self, knowledge: characters.ChampionKnowledge) -> bool:
        position = knowledge.position
        facing = self._get_my_facing(knowledge)
        front_coords = self._get_front_coords(position, facing)
        front_tile = self._get_tile(knowledge, front_coords)

        if front_tile is None:
            return False
        return front_tile.character is not None

    def _enemy_visible(self, knowledge: characters.ChampionKnowledge) -> bool:
        my_position = knowledge.position
        for coords, tile in knowledge.visible_tiles.items():
            if coords == my_position:
                continue
            if tile.character is not None:
                return True
        return False

    def _loot_visible(self, knowledge: characters.ChampionKnowledge) -> bool:
        for _, tile in knowledge.visible_tiles.items():
            if tile.loot is not None:
                return True
        return False

    def _consumable_visible(self, knowledge: characters.ChampionKnowledge) -> bool:
        for _, tile in knowledge.visible_tiles.items():
            if tile.consumable is not None:
                return True
        return False
    
    def _find_menhir(self, knowledge: characters.ChampionKnowledge) -> Optional[Coords]:
        for coords, tile in knowledge.visible_tiles.items():
            if tile.type == "menhir":
                return coords
        return None
    
    def _distance(self, a: Coords, b: Coords) -> int:
        return abs(a.x - b.x) + abs(a.y - b.y)