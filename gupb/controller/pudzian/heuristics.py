from typing import Optional
from gupb.model import characters


class HeuristicLayer:
    def get_action(self, knowledge, memory) -> Optional[characters.Action]:
        # REGUŁA 0: jeśli wróg jest w zasięgu ataku -> ATAKUJ
        if self._enemy_directly_in_front(knowledge, memory):
            return characters.Action.ATTACK

        turn_to_enemy = self._turn_towards_adjacent_enemy(knowledge, memory)
        if turn_to_enemy is not None:
            return turn_to_enemy

        # REGUŁA 0: Oscylowanie -> uciekaj z pętli
        if len(memory.last_positions) >= 6:
            unique = set(memory.last_positions)
            if len(unique) <= 2:
                return self._escape_oscillation(knowledge, memory)
        
        # REGUŁA 1: Mało HP i wróg blisko -> UCIEKAJ (przed atakiem!)
        if memory.last_hp <= 2:
            if self._enemy_in_attack_range(knowledge):
                return self._flee_action(knowledge, memory)
        
        # REGUŁA 2: Wróg bezpośrednio przed nami I mamy dużo HP -> atakuj
        if memory.last_hp >= 4:
            if self._enemy_directly_in_front(knowledge, memory):
                return characters.Action.ATTACK
        
        # REGUŁA 3: Idle za długo
        if memory.idle_turns >= 5:
            return self._force_step(knowledge, memory)

        # REGUŁA 4: W mist -> uciekaj do menhira
        if self._am_i_in_mist(knowledge) and memory.menhir_position is not None:
            return self._move_towards_menhir(knowledge, memory)

        return None
    def _enemy_directly_in_front(self, knowledge, memory) -> bool:
        pos = knowledge.position
        facing = memory.last_facing
        front_pos = (
            pos[0] + facing.value[0],
            pos[1] + facing.value[1]
        )
        tile = knowledge.visible_tiles.get(front_pos)
        if tile and tile.character is not None:
            return True
        return False

    def _turn_towards_adjacent_enemy(self, knowledge, memory) -> Optional[characters.Action]:
        pos = knowledge.position
        px, py = pos[0], pos[1]
        facing = memory.last_facing

        enemies = []
        for coords, tile in knowledge.visible_tiles.items():
            if tile.character is None or coords == pos:
                continue
            dx = coords[0] - px
            dy = coords[1] - py
            if abs(dx) + abs(dy) == 1:
                enemies.append((coords, dx, dy))

        if not enemies:
            return None

        enemies.sort(key=lambda item: (abs(item[1]) + abs(item[2]), item[0][0], item[0][1]))
        _, dx, dy = enemies[0]

        if dx == 1:
            desired = characters.Facing.RIGHT
        elif dx == -1:
            desired = characters.Facing.LEFT
        elif dy == 1:
            desired = characters.Facing.DOWN
        else:
            desired = characters.Facing.UP

        if facing == desired:
            return None
        if facing.turn_left() == desired:
            return characters.Action.TURN_LEFT
        if facing.turn_right() == desired:
            return characters.Action.TURN_RIGHT
        return characters.Action.TURN_RIGHT

    def _escape_oscillation(self, knowledge, memory) -> characters.Action:
        pos = knowledge.position
        facing = memory.last_facing
        visited = set(memory.last_positions)
        
        # Najpierw szukaj pola którego NIE odwiedzaliśmy
        for action, check_facing in [
            (characters.Action.STEP_RIGHT,    facing.turn_right()),
            (characters.Action.STEP_LEFT,     facing.turn_left()),
            (characters.Action.STEP_BACKWARD, facing.opposite()),
            (characters.Action.STEP_FORWARD,  facing),
        ]:
            check_pos = (
                pos[0] + check_facing.value[0],
                pos[1] + check_facing.value[1]
            )
            tile = knowledge.visible_tiles.get(check_pos)
            if (tile is not None and 
                tile.type in ('land', 'forest', 'menhir') and
                check_pos not in visited):  # <- kluczowe: nieodwiedzone
                return action
        
        # Jeśli wszystkie odwiedzone - idź do menhira
        if memory.menhir_position is not None:
            return self._move_towards_menhir(knowledge, memory)
        
        # Ostateczny fallback
        return characters.Action.TURN_LEFT
    def _force_step(self, knowledge, memory) -> characters.Action:
        """Wymuś KROK (zmianę pozycji) - nie obrót"""
        pos = knowledge.position
        facing = memory.last_facing
        
        # Sprawdź wszystkie 4 kierunki i wybierz pierwszy wolny
        for action, check_facing in [
            (characters.Action.STEP_FORWARD, facing),
            (characters.Action.STEP_LEFT,    facing.turn_left()),
            (characters.Action.STEP_RIGHT,   facing.turn_right()),
            (characters.Action.STEP_BACKWARD, facing.opposite()),
        ]:
            check_pos = (
                pos[0] + check_facing.value[0],
                pos[1] + check_facing.value[1]
            )
            tile = knowledge.visible_tiles.get(check_pos)
            if tile is not None and tile.type in ('land', 'forest', 'menhir'):
                return action
        
        # Absolutny fallback
        return characters.Action.TURN_RIGHT

    def _am_i_in_mist(self, knowledge) -> bool:
        my_tile = knowledge.visible_tiles.get(knowledge.position)
        if my_tile:
            for effect in my_tile.effects:
                if 'mist' in effect.type.lower():
                    return True
        return False

    def _move_towards_menhir(self, knowledge, memory) -> Optional[characters.Action]:
        pos = knowledge.position
        target = memory.menhir_position
        dx = target[0] - pos[0]
        dy = target[1] - pos[1]
        facing = memory.last_facing

        if abs(dx) >= abs(dy):
            desired = characters.Facing.RIGHT if dx > 0 else characters.Facing.LEFT
        else:
            desired = characters.Facing.DOWN if dy > 0 else characters.Facing.UP

        if facing == desired:
            return characters.Action.STEP_FORWARD
        elif facing.turn_right() == desired:
            return characters.Action.TURN_RIGHT
        elif facing.turn_left() == desired:
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_RIGHT

    def _enemy_in_attack_range(self, knowledge) -> bool:
        pos = knowledge.position
        px, py = pos[0], pos[1]
        for coords, tile in knowledge.visible_tiles.items():
            if tile.character is not None and coords != pos:
                if abs(coords[0] - px) + abs(coords[1] - py) <= 2:
                    return True
        return False

    def _flee_action(self, knowledge, memory) -> characters.Action:
        pos = knowledge.position
        px, py = pos[0], pos[1]
        nearest_enemy = None
        nearest_dist = float('inf')

        for coords, tile in knowledge.visible_tiles.items():
            if tile.character is not None and coords != pos:
                dist = ((coords[0] - px) ** 2 + (coords[1] - py) ** 2) ** 0.5
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest_enemy = coords

        if nearest_enemy is None:
            return characters.Action.STEP_FORWARD

        dx = nearest_enemy[0] - px
        dy = nearest_enemy[1] - py

        if abs(dx) >= abs(dy):
            desired = characters.Facing.LEFT if dx > 0 else characters.Facing.RIGHT
        else:
            desired = characters.Facing.UP if dy > 0 else characters.Facing.DOWN

        facing = memory.last_facing
        if facing == desired:
            return characters.Action.STEP_FORWARD
        elif facing.turn_right() == desired:
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.TURN_LEFT