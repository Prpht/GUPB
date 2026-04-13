# logic based on page 131 of "Reinforcement Learning: An Introduction"

import random
from collections import defaultdict
from typing import Optional

from .strategy_api import Strategy
from gupb.model import characters, arenas
from gupb.model.coordinates import Coords

from gupb.controller.blade_runner.strategies.navigation import Navigator


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
        self.blocking_tiles: set[Coords] = set()

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.last_state = None
        self.last_action = None
        self.last_position = None
        self.visited = set()
        self.blocking_tiles: set[Coords] = set()

    def decide(
            self, 
            knowledge: characters.ChampionKnowledge,
        ) -> characters.Action:

        current_position = knowledge.position
        current_state = self._build_state(knowledge)


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
                knowledge=knowledge
            )

        self.blocking_tiles = Navigator.update_blocking_tiles(knowledge=knowledge, blocking_tiles=self.blocking_tiles)
        
        fight_action = self._fight_policy(knowledge)

        if not Navigator._is_mist_visible(knowledge) and fight_action is not None:
            action = fight_action
        else:
            action = self._choose_action(current_state, knowledge)

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
        facing = Navigator._get_my_facing(knowledge)

        front_coords = Navigator._get_front_coords(position, facing)
        front_tile = Navigator._get_tile(knowledge, front_coords)

        blocked_front = int(Navigator._is_blocked(front_tile))
        enemy_in_front = int(Navigator._enemy_ahead(knowledge))
        enemy_visible = int(Navigator._enemy_visible(knowledge))
        loot_visible = int(Navigator._loot_visible(knowledge))
        consumable_visible = int(Navigator._consumable_visible(knowledge))
        repeated_position = int(position in self.visited)

        return (
            blocked_front,
            enemy_in_front,
            enemy_visible,
            loot_visible,
            consumable_visible,
            repeated_position,
        )

    def _available_actions(self, knowledge: characters.ChampionKnowledge) -> list[characters.Action]:
        available_actions = [
            characters.Action.ATTACK,
        ]

        if self.last_action is not characters.Action.TURN_LEFT:
            available_actions.append(characters.Action.TURN_RIGHT)

        if self.last_action is not characters.Action.TURN_RIGHT:
            available_actions.append(characters.Action.TURN_LEFT)

        position = knowledge.position

        facing = Navigator._get_my_facing(knowledge=knowledge)
        facing_vec = Navigator._facing_to_vector(facing=facing)

        # FORWARD
        if position + facing_vec not in self.blocking_tiles:
            available_actions.append(characters.Action.STEP_FORWARD)

        # BACKWARD
        back_facing = facing.turn_left().turn_left()
        back_vec = Navigator._facing_to_vector(back_facing)
        if position + back_vec not in self.blocking_tiles:
            available_actions.append(characters.Action.STEP_BACKWARD)

        # LEFT
        left_facing = facing.turn_left()
        left_vec = Navigator._facing_to_vector(left_facing)
        if position + left_vec not in self.blocking_tiles:
            available_actions.append(characters.Action.STEP_LEFT)

        # RIGHT
        right_facing = facing.turn_right()
        right_vec = Navigator._facing_to_vector(right_facing)
        if position + right_vec not in self.blocking_tiles:
            available_actions.append(characters.Action.STEP_RIGHT)

        return available_actions


    def _choose_action(self, state: tuple, knowledge: characters.ChampionKnowledge) -> characters.Action:
        actions = self._available_actions(knowledge=knowledge)

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
        knowledge: characters.ChampionKnowledge
    ) -> None:
        old_q = self._get_q(prev_state, prev_action)
        max_next_q = max(self._get_q(next_state, action) for action in self._available_actions(knowledge))
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

        if Navigator._is_mist_visible(knowledge):
            reward -= 0.4

        if current_position == previous_position:
            reward -= 0.3
        else:
            reward += 0.1

        if previous_action == characters.Action.ATTACK:
            if Navigator._enemy_ahead(knowledge):
                reward += 0.4
            else:
                reward -= 0.2

        if current_position in self.visited:
            reward -= 0.2

        return reward

    def _fight_policy(self, knowledge: characters.ChampionKnowledge) -> Optional[characters.Action]:

        # Don't use fighting policy if enemy is far
        enemy = Navigator._closest_enemy(knowledge)
        if enemy is None:
            return None

        my_pos = knowledge.position

        if Navigator._is_blocking_in_line(my_pos, Coords(*enemy), blocking_tiles=self.blocking_tiles):
            return None

        # Escape if hp is low
        agent_hp = knowledge.visible_tiles[knowledge.position].character.health
        enemy_hp = knowledge.visible_tiles[Coords(*enemy)].character.health

        if agent_hp < min(enemy_hp, characters.CHAMPION_STARTING_HP/3):
            return None
        
        # Fight
        if Navigator._enemy_ahead(knowledge):
            return characters.Action.ATTACK

        dx = enemy[0] - my_pos[0]
        dy = enemy[1] - my_pos[1]

        if abs(dx) > abs(dy):
            target = characters.Facing.RIGHT if dx > 0 else characters.Facing.LEFT
        else:
            target = characters.Facing.DOWN if dy > 0 else characters.Facing.UP


        facing = Navigator._get_my_facing(knowledge)
        if facing == target:
            return random.choice([characters.Action.STEP_FORWARD, characters.Action.ATTACK])
        else:
            return None
    