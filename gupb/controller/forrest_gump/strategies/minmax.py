from gupb.controller.forrest_gump.strategies import Strategy
from gupb.controller.forrest_gump.utils import CharacterInfo, distance_to, next_facing, next_step, find_path, \
    next_pos_to_action, closest_opposite
from gupb.model import tiles, characters, coordinates, arenas, weapons


ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.ATTACK
]


WEAPONS = {
    'knife': weapons.Knife,
    'sword': weapons.Sword,
    'bow': weapons.Bow,
    'bow_loaded': weapons.Bow,
    'bow_unloaded': weapons.Bow,
    'axe': weapons.Axe,
    'amulet': weapons.Amulet
}


class MinMax(Strategy):
    def __init__(self, arena_description: arenas.ArenaDescription, enter_distance: int = 5, max_depth: int = 3) -> None:
        super().__init__(arena_description)
        self.enter_distance = enter_distance
        self.max_depth = max_depth

    def enter(self) -> None:
        pass

    def should_enter(self, coords: coordinates.Coords, tile: tiles.TileDescription, character_info: CharacterInfo) -> bool:
        if tile.character:
            self.distance = distance_to(self.matrix, coords, character_info.position)
            cut_positions = WEAPONS[tile.character.weapon.name].cut_positions(self.arena.terrain, character_info.position, character_info.facing)

            if self.distance <= self.enter_distance or character_info.position in cut_positions:
                self.enemy = tile.character
                self.enemy_position = coords
                self.enemy_age = 2
                return True

        return False

    def should_leave(self, character_info: CharacterInfo) -> bool:
        return self.enemy_age <= 0 or self.distance > self.enter_distance

    def left(self) -> None:
        pass

    def next_action(self, character_info: CharacterInfo) -> characters.Action:
        def minimax_alpha_beta_pruning(state: dict, depth: int, alpha: float, beta: float, maximizing_player: bool) -> tuple:
            if depth == 0 or state['forrest_health'] <= 0 or state['enemy_health'] <= 0:
                return evaluate_state(state), None

            if maximizing_player:
                max_eval = -float('inf')
                best_move = None

                for action in ACTIONS:
                    new_state = make_move(state, action, maximizing_player)
                    eval, _ = minimax_alpha_beta_pruning(new_state, depth - 1, alpha, beta, not maximizing_player)

                    if eval > max_eval:
                        best_move = action
                        max_eval = eval

                    alpha = max(alpha, max_eval)

                    if beta <= alpha:
                        break

                return max_eval, best_move
            else:
                min_eval = float('inf')

                for action in ACTIONS:
                    new_state = make_move(state, action, maximizing_player)
                    eval, _ = minimax_alpha_beta_pruning(new_state, depth - 1, alpha, beta, not maximizing_player)
                    min_eval = min(min_eval, eval)
                    beta = min(beta, min_eval)

                    if beta <= alpha:
                        break

                return min_eval, None

        def make_move(state: dict, action: characters.Action, maximizing_player: bool) -> dict:
            def move(position_p, facing_p, weapon_p, position_e, health_e) -> tuple:
                if action == characters.Action.ATTACK:
                    if position_e in WEAPONS[weapon_p].cut_positions(self.arena.terrain, position_p, facing_p):
                        return position_p, facing_p, health_e - WEAPONS[weapon_p].cut_effect().damage
                    else:
                        return position_p, facing_p, health_e
                elif action in [characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]:
                    return position_p, next_facing(facing_p, action), health_e
                else:
                    next_p = next_step(position_p, facing_p, action)

                    if [next_p.x, next_p.y] not in self.fields:
                        return position_p, facing_p, health_e

                    return next_p, facing_p, health_e

            if maximizing_player:
                enemy_position, enemy_facing, enemy_health = move(
                    state['forrest_position'], state['forrest_facing'], character_info.weapon,
                    state['enemy_position'], state['enemy_health']
                )
                return {
                    'forrest_position': enemy_position,
                    'forrest_facing': enemy_facing,
                    'forrest_health': state['forrest_health'],
                    'enemy_position': state['enemy_position'],
                    'enemy_facing': state['enemy_facing'],
                    'enemy_health': enemy_health
                }
            else:
                enemy_position, enemy_facing, new_health = move(
                    state['enemy_position'], state['enemy_facing'], self.enemy.weapon.name,
                    state['forrest_position'], state['forrest_health']
                )
                return {
                    'forrest_position': state['forrest_position'],
                    'forrest_facing': state['forrest_facing'],
                    'forrest_health': new_health,
                    'enemy_position': enemy_position,
                    'enemy_facing': enemy_facing,
                    'enemy_health': state['enemy_health']
                }

        def evaluate_state(state: dict) -> float:
            return state['forrest_health'] - state['enemy_health']

        initial_state = {
            'forrest_position': character_info.position,
            'forrest_facing': character_info.facing,
            'forrest_health': character_info.health,
            'enemy_position': self.enemy_position,
            'enemy_facing': self.enemy.facing,
            'enemy_health': self.enemy.health
        }

        self.enemy_age -= 1
        eval, action = minimax_alpha_beta_pruning(initial_state, self.max_depth, -float('inf'), float('inf'), True)

        if eval > 0:
            return action

        if eval == 0:
            destination = self.enemy_position
        else:
            cut_positions = WEAPONS[self.enemy.weapon.name].cut_positions(self.arena.terrain, self.enemy_position, self.enemy.facing)

            if character_info.position in cut_positions:
                safe_positions = self.fields.copy()

                for pos in cut_positions:
                    if pos in safe_positions:
                        safe_positions.remove([pos.x, pos.y])

                safe_positions = [coordinates.Coords(pos[0], pos[1]) for pos in safe_positions]
                destination = min([(distance_to(self.matrix, character_info.position, pos), pos) for pos in safe_positions])[1]
            else:
                destination = closest_opposite(self.fields, character_info.position, self.enemy_position)
                destination = coordinates.Coords(destination[0], destination[1])

        path = find_path(self.matrix, character_info.position, destination)
        next_pos = path[1] if len(path) > 1 else path[0]
        return next_pos_to_action(next_pos.x, next_pos.y, character_info.facing, character_info.position, len(path) > 2)

    @property
    def priority(self) -> int:
        return 6
