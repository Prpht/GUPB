from typing import Optional, List
from gupb.model import arenas, characters, coordinates


POTION_PICKUP_COOLDOWN_TURNS = 5


class BotMemory:
    def __init__(self):
        # Bufor treningowy - inicjalizowany raz, czyszczony przez train.py
        self.states: list = []
        self.actions: list = []
        self.log_probs: list = []
        self.values: list = []
        self.rewards: list = []
        self.dones: list = []
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.turn_no: int = 0
        self.last_hp: int = characters.CHAMPION_STARTING_HP
        self.last_potion_pick_turn: int = -POTION_PICKUP_COOLDOWN_TURNS
        self.last_facing: characters.Facing = characters.Facing.UP
        self.took_damage_last_turn: bool = False
        self.idle_turns: int = 0
        self.last_position: Optional[coordinates.Coords] = None
        self.last_action: Optional[int] = None

        # Wrogowie
        self.enemies_seen_total: int = 0
        self.turns_since_last_seen_enemy: int = 0

        # Menhir/strefa
        self.menhir_position: Optional[coordinates.Coords] = None

        # Historia pozycji do wykrywania oscylacji
        self.last_positions: List = []

        # Reward shaping
        self.prev_dist_to_menhir: Optional[float] = None
        self.attacks_landed: int = 0
        self.prev_enemy_dist = None
        self.prev_enemy_hp = {}


    def update(self, knowledge: characters.ChampionKnowledge) -> None:
        self.turn_no += 1
    
        # Aktualizuj HP i facing z widocznego kafelka
        my_tile = knowledge.visible_tiles.get(knowledge.position)
        if my_tile and my_tile.character:
            current_hp = my_tile.character.health
            self.took_damage_last_turn = current_hp < self.last_hp
            if current_hp > self.last_hp:
                self.last_potion_pick_turn = self.turn_no
            self.last_hp = current_hp
            self.last_facing = my_tile.character.facing

        # Idle tracking
        if self.last_position == knowledge.position:
            self.idle_turns += 1
        else:
            self.idle_turns = 0
        self.last_position = knowledge.position

        # Historia pozycji - ostatnie 6
        self.last_positions.append(knowledge.position)
        if len(self.last_positions) > 6:
            self.last_positions.pop(0)

        # Wrogowie
        visible_enemies = self._count_visible_enemies(knowledge)
        if visible_enemies > 0:
            self.enemies_seen_total += visible_enemies
            self.turns_since_last_seen_enemy = 0
        else:
            self.turns_since_last_seen_enemy += 1

        # Menhir - szukaj w visible_tiles
        for coords, tile in knowledge.visible_tiles.items():
            if tile.type == 'menhir':
                self.menhir_position = coords
                break
        current_enemy_hp = {}

        for coords, tile in knowledge.visible_tiles.items():
            if tile.character is not None and coords != knowledge.position:
                current_enemy_hp[coords] = tile.character.health

        self.current_enemy_hp = current_enemy_hp

    def is_potion_cooldown_active(self) -> bool:
        turns_since_pickup = self.turn_no - self.last_potion_pick_turn
        return turns_since_pickup < POTION_PICKUP_COOLDOWN_TURNS

    def _count_visible_enemies(
            self,
            knowledge: characters.ChampionKnowledge
    ) -> int:
        count = 0
        for coords, tile in knowledge.visible_tiles.items():
            if tile.character is not None and coords != knowledge.position:
                count += 1
        return count

    def compute_step_reward(self, knowledge, action_idx) -> float:
        reward = 0.0
        pos = knowledge.position
        my_tile = knowledge.visible_tiles.get(pos)

        # Przeżycie
        reward += 0.02

        # Mist
        if my_tile:
            for effect in my_tile.effects:
                if 'mist' in effect.type.lower():
                    reward -= 1.0
                    break

        # Obrażenia
        if self.took_damage_last_turn:
            reward -= 0.2

        # Idle
        if self.idle_turns >= 3:
            reward -= min(0.5 * self.idle_turns, 2.5)

        # DO_NOTHING
        if action_idx == 7:
            reward -= 0.5

        # Oscylowanie
        if len(self.last_positions) >= 6:
            if len(set(self.last_positions)) <= 2:
                reward -= 0.5
        # Menhir
        if self.menhir_position is not None:
            dist = ((pos[0] - self.menhir_position[0]) ** 2 +
                    (pos[1] - self.menhir_position[1]) ** 2) ** 0.5
            if self.prev_dist_to_menhir is not None:
                if dist < self.prev_dist_to_menhir:
                    reward += 0.7
                elif dist > self.prev_dist_to_menhir:
                    reward -= 0.2
            self.prev_dist_to_menhir = dist
        if hasattr(self, "kill_reward_pending") and self.kill_reward_pending:
            reward += 6.0
            self.kill_reward_pending = False
        # --- REAL DAMAGE REWARD ---
        damage_dealt = 0
        visible_enemies = 0

        current_enemy_hp = {}

        for coords, tile in knowledge.visible_tiles.items():
            if tile.character is not None and coords != pos:
                visible_enemies += 1
                current_enemy_hp[coords] = tile.character.health

        # policz realny damage
        if hasattr(self, "prev_enemy_hp"):
            for coords, hp in current_enemy_hp.items():
                if coords in self.prev_enemy_hp:
                    hp_before = self.prev_enemy_hp[coords]
                    if hp < hp_before:
                        damage_dealt += (hp_before - hp)
        if hasattr(self, "prev_enemy_hp"):
            for coords, hp_before in self.prev_enemy_hp.items():
                if coords not in current_enemy_hp:
                    # wróg zniknął (prawdopodobnie zginął)
                    reward += 5.0
        # umiarkowana nagroda za damage
        if action_idx == 6 and damage_dealt > 0:
            reward += damage_dealt * 7.0
            self.attacks_landed += damage_dealt

        # lekka nagroda za bycie w kontakcie
        if visible_enemies > 0:
            reward += 0.15

        # lekka kara za oddalanie się
        # --- AGRESJA: nagroda za skracanie dystansu ---
        if visible_enemies > 0:
            my_x, my_y = pos[0], pos[1]
            min_dist = min(
                abs(coords[0] - my_x) + abs(coords[1] - my_y)
                for coords in current_enemy_hp
            )

            if self.prev_enemy_dist is not None:
                if min_dist < self.prev_enemy_dist:
                    reward += 1.0      # <- zwiększamy
                elif min_dist > self.prev_enemy_dist:
                    reward -= 1.0

            self.prev_enemy_dist = min_dist

        # kara za atak bez wroga
        if action_idx == 6 and visible_enemies == 0:
            reward -= 0.5

        self.prev_enemy_hp = current_enemy_hp.copy()
        return reward