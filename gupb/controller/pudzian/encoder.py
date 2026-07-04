import numpy as np
from gupb.model import characters

WEAPON_TO_IDX = {
    'knife': 0,
    'sword': 1,
    'bow_unloaded': 2,
    'bow_loaded': 3,
    'axe': 4,
    'amulet': 5,
    'scroll': 6,
}
NUM_WEAPONS = len(WEAPON_TO_IDX)

FACING_TO_IDX = {
    characters.Facing.UP: 0,
    characters.Facing.RIGHT: 1,
    characters.Facing.DOWN: 2,
    characters.Facing.LEFT: 3,
}

MAX_MAP_SIZE = 50.0
MAX_HP = 8.0
MAX_CHAMPIONS = 10.0
MAX_TURNS = 300.0
MAX_DIST = 50.0


class StateEncoder:
    def encode(self, knowledge: characters.ChampionKnowledge, memory) -> np.ndarray:
        features = []
        features += self._encode_self(knowledge, memory)
        features += self._encode_enemies(knowledge)
        features += self._encode_loot(knowledge, memory)
        features += self._encode_potion(knowledge, memory)
        features += self._encode_zone(knowledge, memory)
        features += self._encode_context(knowledge, memory)
        assert len(features) == 35, f"Feature size mismatch: {len(features)}"
        return np.array(features, dtype=np.float32)

    def _encode_self(self, knowledge, memory) -> list:
        pos = knowledge.position
        pos_x_norm = pos[0] / MAX_MAP_SIZE
        pos_y_norm = pos[1] / MAX_MAP_SIZE

        my_tile = knowledge.visible_tiles.get(pos)
        if my_tile and my_tile.character:
            hp_norm = my_tile.character.health / MAX_HP
            facing = my_tile.character.facing
            weapon_name = my_tile.character.weapon.name
        else:
            hp_norm = memory.last_hp / MAX_HP
            facing = memory.last_facing
            weapon_name = 'knife'

        facing_idx = FACING_TO_IDX.get(facing, 0)
        facing_angle = facing_idx * (np.pi / 2)
        facing_sin = float(np.sin(facing_angle))
        facing_cos = float(np.cos(facing_angle))

        weapon_idx = WEAPON_TO_IDX.get(weapon_name, 0)
        weapon_norm = weapon_idx / NUM_WEAPONS
        idle_norm = min(memory.idle_turns / 16.0, 1.0)

        return [hp_norm, facing_sin, facing_cos, weapon_norm, pos_x_norm, pos_y_norm, idle_norm]

    def _encode_enemies(self, knowledge) -> list:
        my_pos = knowledge.position
        my_x, my_y = my_pos[0], my_pos[1]
        enemies = []

        for coords, tile in knowledge.visible_tiles.items():
            if tile.character is not None and coords != my_pos:
                cx, cy = coords[0], coords[1]
                dx = cx - my_x
                dy = cy - my_y
                dist = (dx ** 2 + dy ** 2) ** 0.5
                weapon_name = tile.character.weapon.name
                weapon_idx = WEAPON_TO_IDX.get(weapon_name, 0)

                enemy_facing = tile.character.facing
                enemy_facing_vec = enemy_facing.value
                dot = (enemy_facing_vec[0] * (-dx) + enemy_facing_vec[1] * (-dy))
                enemy_facing_aligned = 1.0 if dot > 0 else 0.0

                enemies.append({
                    'dist': dist,
                    'dx': dx,
                    'dy': dy,
                    'hp': tile.character.health,
                    'weapon_idx': weapon_idx,
                    'facing_aligned': enemy_facing_aligned,
                })

        enemies.sort(key=lambda e: e['dist'])

        if len(enemies) >= 1:
            e = enemies[0]
            nearest = [
                1.0,
                e['dist'] / MAX_DIST,
                e['dx'] / MAX_DIST,
                e['dy'] / MAX_DIST,
                e['hp'] / MAX_HP,
                e['weapon_idx'] / NUM_WEAPONS,
                e['facing_aligned'],
            ]
        else:
            nearest = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        if len(enemies) >= 2:
            e = enemies[1]
            second = [1.0, e['dist'] / MAX_DIST, e['dx'] / MAX_DIST, e['dy'] / MAX_DIST]
        else:
            second = [0.0, 0.0, 0.0, 0.0]

        return nearest + second

    def _encode_loot(self, knowledge, memory) -> list:
        my_pos = knowledge.position
        my_x, my_y = my_pos[0], my_pos[1]
        my_tile = knowledge.visible_tiles.get(my_pos)

        current_weapon = 'knife'
        if my_tile and my_tile.character:
            current_weapon = my_tile.character.weapon.name
        current_weapon_idx = WEAPON_TO_IDX.get(current_weapon, 0)

        weapons_nearby = []
        for coords, tile in knowledge.visible_tiles.items():
            if tile.loot is not None:
                cx, cy = coords[0], coords[1]
                dx = cx - my_x
                dy = cy - my_y
                dist = (dx ** 2 + dy ** 2) ** 0.5
                loot_weapon_idx = WEAPON_TO_IDX.get(tile.loot.name, 0)
                if tile.loot.name == 'amulet':
                    continue
                if loot_weapon_idx > current_weapon_idx:
                    weapons_nearby.append((dist, dx, dy, loot_weapon_idx))

        if weapons_nearby:
            weapons_nearby.sort()
            dist, dx, dy, w_idx = weapons_nearby[0]
            return [1.0, dist / MAX_DIST, dx / MAX_DIST, dy / MAX_DIST, w_idx / NUM_WEAPONS]
        else:
            return [0.0, 0.0, 0.0, 0.0, 0.0]

    def _encode_potion(self, knowledge, memory) -> list:
        my_pos = knowledge.position
        my_x, my_y = my_pos[0], my_pos[1]
        potions = []

        for coords, tile in knowledge.visible_tiles.items():
            if tile.consumable is not None:
                cx, cy = coords[0], coords[1]
                dx = cx - my_x
                dy = cy - my_y
                dist = (dx ** 2 + dy ** 2) ** 0.5
                potions.append((dist, dx, dy))

        czy_mam_malo_hp = 1.0 if memory.last_hp <= 3 else 0.0
        can_seek_potion = not memory.is_potion_cooldown_active()

        if potions and can_seek_potion:
            potions.sort()
            dist, dx, dy = potions[0]
            return [1.0, dist / MAX_DIST, czy_mam_malo_hp]
        else:
            return [0.0, 0.0, czy_mam_malo_hp]

    def _encode_zone(self, knowledge, memory) -> list:
        my_pos = knowledge.position
        my_x, my_y = my_pos[0], my_pos[1]
        my_tile = knowledge.visible_tiles.get(my_pos)

        am_i_in_mist = 0.0
        if my_tile:
            for effect in my_tile.effects:
                if 'mist' in effect.type.lower():
                    am_i_in_mist = 1.0
                    break

        mist_count = 0
        for tile in knowledge.visible_tiles.values():
            for effect in tile.effects:
                if 'mist' in effect.type.lower():
                    mist_count += 1
                    break

        mist_tiles_norm = min(mist_count / 20.0, 1.0)

        if memory.menhir_position is not None:
            menhir_dx = (memory.menhir_position[0] - my_x) / MAX_DIST
            menhir_dy = (memory.menhir_position[1] - my_y) / MAX_DIST
            czy_widze_menhir = 1.0
        else:
            menhir_dx = 0.0
            menhir_dy = 0.0
            czy_widze_menhir = 0.0

        return [am_i_in_mist, mist_tiles_norm, czy_widze_menhir, menhir_dx, menhir_dy]

    def _encode_context(self, knowledge, memory) -> list:
        champions_alive_norm = knowledge.no_of_champions_alive / MAX_CHAMPIONS
        turn_norm = min(memory.turn_no / MAX_TURNS, 1.0)
        turns_since_enemy_norm = min(memory.turns_since_last_seen_enemy / 50.0, 1.0)
        enemies_seen_norm = min(memory.enemies_seen_total / 20.0, 1.0)
        return [champions_alive_norm, turn_norm, turns_since_enemy_norm, enemies_seen_norm]