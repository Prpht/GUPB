from __future__ import annotations

import random
from collections import defaultdict, deque
from typing import Optional

from gupb.model import arenas, characters
from gupb.model.coordinates import Coords

class QLearningStrategy:
    def __init__(self) -> None:
        self.alpha = 0.25
        self.gamma = 0.95
        self.epsilon = 0.05
        self.epsilon_min = 0.02
        self.epsilon_decay = 0.995

        self.q_values: dict[tuple[tuple, characters.Action], float] = defaultdict(float)

        self.previous_state: Optional[tuple] = None
        self.previous_action: Optional[characters.Action] = None
        self.previous_position: Optional[Coords] = None
        self.previous_health: Optional[int] = None
        self.previous_enemy_ahead: Optional[bool] = None

        self.visited_positions: set[Coords] = set()
        self.recent_positions = deque(maxlen=8)

        self.random = random.Random()

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.previous_state = None
        self.previous_action = None
        self.previous_position = None
        self.previous_health = None
        self.previous_enemy_ahead = None

        self.visited_positions.clear()
        self.recent_positions.clear()

        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        position = knowledge.position
        health = self._my_health(knowledge)
        state = self._build_state(knowledge)
        available_actions = self._available_actions(knowledge)

        reward = self._compute_reward(
            knowledge=knowledge,
            previous_position=self.previous_position,
            current_position=position,
            previous_action=self.previous_action,
            current_health=health,
        )

        if self.previous_state is not None and self.previous_action is not None:
            self._update_q_value(
                previous_state=self.previous_state,
                previous_action=self.previous_action,
                reward=reward,
                current_state=state,
                current_available_actions=available_actions,
            )

        action = self._choose_action(state, available_actions)

        self.previous_state = state
        self.previous_action = action
        self.previous_position = position
        self.previous_health = health
        self.previous_enemy_ahead = self._is_enemy_ahead(knowledge)

        self.visited_positions.add(position)
        self.recent_positions.append(position)

        return action

    def praise(self, score: int) -> None:
        if self.previous_state is None or self.previous_action is None:
            return

        old_value = self._q_value(self.previous_state, self.previous_action)
        final_reward = max(-20.0, min(30.0, float(score)))
        self.q_values[(self.previous_state, self.previous_action)] = (
            old_value + self.alpha * (final_reward - old_value)
        )

    def _build_state(self, knowledge: characters.ChampionKnowledge) -> tuple:
        position = knowledge.position
        facing = self._my_facing(knowledge)

        front_position = self._front_position(position, facing)
        front_tile = self._tile_at(knowledge, front_position)

        blocked_front = int(self._is_blocked(front_tile))
        enemy_ahead = int(self._is_enemy_ahead(knowledge))
        enemy_visible = int(self._is_enemy_visible(knowledge))
        loot_visible = int(self._is_loot_visible(knowledge))
        consumable_visible = int(self._is_consumable_visible(knowledge))
        loot_ahead = int(self._is_loot_ahead(knowledge))
        consumable_ahead = int(self._is_consumable_ahead(knowledge))
        visited_before = int(position in self.visited_positions)
        looped_recently = int(position in list(self.recent_positions)[:-1])
        low_health = int(self._my_health(knowledge) <= 3)
        mist_visible = int(self._is_mist_visible(knowledge))

        return (
            blocked_front,
            enemy_ahead,
            enemy_visible,
            loot_visible,
            consumable_visible,
            loot_ahead,
            consumable_ahead,
            visited_before,
            looped_recently,
            low_health,
            mist_visible,
        )

    # Zwraca listę akcji dozwolonych w bieżącej sytuacji.
    # Agent nie próbuje iść do przodu, jeśli pole jest zablokowane,
    # i nie atakuje, jeśli nie ma wroga przed sobą.
    def _available_actions(
        self,
        knowledge: characters.ChampionKnowledge,
    ) -> list[characters.Action]:
        actions = [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
        ]

        position = knowledge.position
        facing = self._my_facing(knowledge)
        front_position = self._front_position(position, facing)
        front_tile = self._tile_at(knowledge, front_position)

        if not self._is_blocked(front_tile):
            actions.append(characters.Action.STEP_FORWARD)

        if self._is_enemy_ahead(knowledge):
            actions.append(characters.Action.ATTACK)

        return actions

    # Wybiera akcję metodą epsilon-greedy:
    # czasem losowo eksploruje, a czasem wybiera najlepszą znaną akcję,
    # dodatkowo z lekkim biasem heurystycznym.
    def _choose_action(
        self,
        state: tuple,
        available_actions: list[characters.Action],
    ) -> characters.Action:
        blocked_front = bool(state[0])
        enemy_ahead = bool(state[1])
        enemy_visible = bool(state[2])
        loot_visible = bool(state[3])
        consumable_visible = bool(state[4])
        loot_ahead = bool(state[5])
        consumable_ahead = bool(state[6])
        looped_recently = bool(state[8])
        low_health = bool(state[9])

        if enemy_ahead and characters.Action.ATTACK in available_actions:
            return characters.Action.ATTACK

        if self.random.random() < self.epsilon:
            return self.random.choice(available_actions)

        action_bias = {action: 0.0 for action in available_actions}

        if blocked_front:
            if characters.Action.TURN_LEFT in action_bias:
                action_bias[characters.Action.TURN_LEFT] += 0.20
            if characters.Action.TURN_RIGHT in action_bias:
                action_bias[characters.Action.TURN_RIGHT] += 0.20

        if loot_ahead and characters.Action.STEP_FORWARD in action_bias:
            action_bias[characters.Action.STEP_FORWARD] += 0.50

        if consumable_ahead and characters.Action.STEP_FORWARD in action_bias:
            action_bias[characters.Action.STEP_FORWARD] += 0.80 if low_health else 0.40

        if not blocked_front and enemy_visible and characters.Action.STEP_FORWARD in action_bias:
            action_bias[characters.Action.STEP_FORWARD] += 0.15

        if (
            not blocked_front
            and (loot_visible or consumable_visible)
            and characters.Action.STEP_FORWARD in action_bias
        ):
            action_bias[characters.Action.STEP_FORWARD] += 0.10

        if looped_recently:
            if characters.Action.STEP_FORWARD in action_bias:
                action_bias[characters.Action.STEP_FORWARD] += 0.20
            if characters.Action.TURN_LEFT in action_bias:
                action_bias[characters.Action.TURN_LEFT] -= 0.05
            if characters.Action.TURN_RIGHT in action_bias:
                action_bias[characters.Action.TURN_RIGHT] -= 0.05

        best_value = max(
            self._q_value(state, action) + action_bias[action]
            for action in available_actions
        )
        best_actions = [
            action
            for action in available_actions
            if self._q_value(state, action) + action_bias[action] == best_value
        ]
        return self.random.choice(best_actions)

    def _update_q_value(
        self,
        previous_state: tuple,
        previous_action: characters.Action,
        reward: float,
        current_state: tuple,
        current_available_actions: list[characters.Action],
    ) -> None:
        old_value = self._q_value(previous_state, previous_action)
        best_next_value = max(
            (self._q_value(current_state, action) for action in current_available_actions),
            default=0.0,
        )
        new_value = old_value + self.alpha * (
            reward + self.gamma * best_next_value - old_value
        )
        self.q_values[(previous_state, previous_action)] = new_value

    # Zwraca aktualną wartość Q dla pary (stan, akcja).
    def _q_value(self, state: tuple, action: characters.Action) -> float:
        return self.q_values[(state, action)]

    # Liczy nagrodę za poprzedni krok na podstawie ruchu, zdrowia,
    # widoczności mgły i unikania zapętleń.
    def _compute_reward(
        self,
        knowledge: characters.ChampionKnowledge,
        previous_position: Optional[Coords],
        current_position: Coords,
        previous_action: Optional[characters.Action],
        current_health: int,
    ) -> float:
        if previous_position is None:
            return 0.0

        reward = -0.03

        if self._is_mist_visible(knowledge):
            reward -= 0.35

        if current_position == previous_position:
            reward -= 0.35
        else:
            reward += 0.10

        if previous_action == characters.Action.ATTACK:
            if self.previous_enemy_ahead:
                reward += 0.40
            else:
                reward -= 0.25

        if self.previous_health is not None:
            reward += 1.2 * (current_health - self.previous_health)

        if current_position in self.visited_positions:
            reward -= 0.08
        else:
            reward += 0.05

        if current_position in list(self.recent_positions)[:-1]:
            reward -= 0.15

        return reward

    # Zwraca aktualne zdrowie.
    def _my_health(self, knowledge: characters.ChampionKnowledge) -> int:
        return knowledge.visible_tiles[knowledge.position].character.health

    # Zwraca aktualny kierunek skierowania postaci.
    def _my_facing(self, knowledge: characters.ChampionKnowledge):
        return knowledge.visible_tiles[knowledge.position].character.facing

    # Zwraca nazwę kontrolera postaci.
    def _my_controller_name(self, knowledge: characters.ChampionKnowledge) -> str:
        return knowledge.visible_tiles[knowledge.position].character.controller_name

    # Zamienia kierunek skierowania na wektor przesunięcia.
    def _facing_vector(self, facing) -> Coords:
        if facing == characters.Facing.UP:
            return Coords(0, -1)
        if facing == characters.Facing.DOWN:
            return Coords(0, 1)
        if facing == characters.Facing.LEFT:
            return Coords(-1, 0)
        return Coords(1, 0)

    # Zwraca współrzędne pola bezpośrednio przed postacią.
    def _front_position(self, position: Coords, facing) -> Coords:
        return position + self._facing_vector(facing)

    # Zwraca opis kafelka pod wskazaną pozycją, jeśli jest widoczny.
    def _tile_at(self, knowledge: characters.ChampionKnowledge, position: Coords):
        return knowledge.visible_tiles.get(position)

    # Sprawdza, czy kafelek jest zablokowany.
    def _is_blocked(self, tile) -> bool:
        if tile is None:
            return True
        if tile.type in {"wall", "sea"}:
            return True
        if tile.character is not None:
            return True
        return False

    # Sprawdza, czy bezpośrednio przed postacią znajduje się wróg.
    def _is_enemy_ahead(self, knowledge: characters.ChampionKnowledge) -> bool:
        position = knowledge.position
        facing = self._my_facing(knowledge)
        front_position = self._front_position(position, facing)
        front_tile = self._tile_at(knowledge, front_position)

        if front_tile is None or front_tile.character is None:
            return False

        return front_tile.character.controller_name != self._my_controller_name(knowledge)

    # Sprawdza, czy gdziekolwiek w widocznym obszarze znajduje się wróg.
    def _is_enemy_visible(self, knowledge: characters.ChampionKnowledge) -> bool:
        my_position = knowledge.position
        my_name = self._my_controller_name(knowledge)

        for position, tile in knowledge.visible_tiles.items():
            if position == my_position:
                continue
            if tile.character is not None and tile.character.controller_name != my_name:
                return True
        return False

    # Sprawdza, czy w widocznym obszarze znajduje się jakikolwiek loot.
    def _is_loot_visible(self, knowledge: characters.ChampionKnowledge) -> bool:
        for tile in knowledge.visible_tiles.values():
            if tile.loot is not None:
                return True
        return False

    # Sprawdza, czy w widocznym obszarze znajduje się jakikolwiek consumable.
    def _is_consumable_visible(self, knowledge: characters.ChampionKnowledge) -> bool:
        for tile in knowledge.visible_tiles.values():
            if tile.consumable is not None:
                return True
        return False

    # Sprawdza, czy na polu przed postacią znajduje się loot.
    def _is_loot_ahead(self, knowledge: characters.ChampionKnowledge) -> bool:
        position = knowledge.position
        facing = self._my_facing(knowledge)
        front_tile = self._tile_at(knowledge, self._front_position(position, facing))
        return front_tile is not None and front_tile.loot is not None

    # Sprawdza, czy na polu przed postacią znajduje się consumable.
    def _is_consumable_ahead(self, knowledge: characters.ChampionKnowledge) -> bool:
        position = knowledge.position
        facing = self._my_facing(knowledge)
        front_tile = self._tile_at(knowledge, self._front_position(position, facing))
        return front_tile is not None and front_tile.consumable is not None

    # Sprawdza, czy w aktualnie widocznych polach widoczna jest mgła.
    def _is_mist_visible(self, knowledge: characters.ChampionKnowledge) -> bool:
        return any(
            any(effect.type == "mist" for effect in tile.effects)
            for tile in knowledge.visible_tiles.values()
        )