from gupb.controller.norgul.memory import Memory
from gupb.controller.norgul.movement import MotorCortex
from gupb.controller.norgul.navigation import Navigator
from gupb.controller.norgul.misc import manhattan_dist, max_dist, get_weapon
from gupb.controller.norgul.config import COMBAT_MAX_DIST, WEAPON_VS_WEAPON_CHANCES

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import weapons

from math import inf
from typing import Set, Tuple


# -------------------
# Combat engine class
# -------------------

# Represents character's ability to fight with other players
class CombatEngine:

    def __init__(self, memory: Memory, navigator: Navigator, motor: MotorCortex):
        self.memory = memory
        self.navigator = navigator
        self.motor = motor
    
    # -------------------------------------
    # Combat engine - searching for targets
    # -------------------------------------

    # Tries to find a suitable target for Norgul to kill
    # - Can be customized with additional arguments (for example, whether to attack enemies near mist or not)
    def find_target(self, avoid_mist: bool = True) -> Tuple[coordinates.Coords, float] | None:
        ''' Returns a tuple of the best target to attack as well as evaluation of chances. 

            If there are no suitable targets, it returns a single None.
        '''

        # For each player, we consider 3 factors:
        # - Distance: the further from Norgul, the lower the priority
        # - HP ratio: our_hp / enemy_hp defines chances of winning the fight
        # - Weapon difference: each weapon vs weapon combination defines a static chance of winning the fight

        best_target = None
        best_eval = 0.0

        # Iterate over all seen characters
        for sq, enemy in self.memory.arena.players.items():
            # Do not consider fighting with yourself ;)
            if sq == self.memory.pos:
                continue

            # Check conditions for even considering player as a target
            # - Omit players hiding in the forest (they are immortal)
            # - Decide whether to attack players near mist
            if self.memory.arena[sq].type == "forest":
                continue
            
            nearby = [coordinates.Coords(sq[0] + i, sq[1] + j) for i in range(-1, 2) for j in range(-1, 2)]
            if avoid_mist and any(tile in self.memory.arena and ("mist",) in self.memory.arena[tile].effects for tile in nearby):
                continue

            eval = 1.0

            # Consider distance between players
            dist = manhattan_dist(self.memory.pos, sq)
            eval *= max(0.01, (COMBAT_MAX_DIST - dist + 1) / COMBAT_MAX_DIST)

            # Consider HP ratio
            eval *= max(enemy.health / 10, self.memory.hp) / max(self.memory.hp / 10, enemy.health)

            # Consider weapon difference
            weapon_vs_weapon = f"{self.memory.weapon_name}_vs_{enemy.weapon.name}"
            eval *= WEAPON_VS_WEAPON_CHANCES[weapon_vs_weapon]

            if eval > best_eval:
                best_eval = eval
                best_target = sq
        
        return best_target, best_eval
    
    # ------------------------------
    # Combat engine - combat control
    # ------------------------------

    # Produces an optimal action in order to defeat given player
    def fight_control(self, enemy_sq: coordinates.Coords,
                      safe_mode: bool = False) -> characters.Action:
        # Fist of all, let's identify the player we want to attack
        enemy = self.memory.arena[enemy_sq].character

        # And obtain some information about us and enemy
        our_weapon = get_weapon(self.memory.weapon_name)
        enemy_weapon = get_weapon(enemy.weapon.name)
        our_attack_area = our_weapon.cut_positions(self.memory.terrain, self.memory.pos, self.memory.dir)
        enemy_attack_area = enemy_weapon.cut_positions(self.memory.terrain, enemy_sq, enemy.facing)

        # Case 1 - we can already attack the enemy
        # - Let's smash him hard...
        # - TODO: Might cancel out "safe" fight strategy in some cases
        if enemy_sq in our_attack_area:
            return characters.Action.ATTACK

        # Safe spots are square from which we can attack enemy, but he cannot attack us
        # - Only considered if safe_mode flag is set to True
        target_spots: Set[coordinates.Coords] = set()

        if safe_mode:
            # TODO: Implement that
            pass
        else:
            target_spots.add(enemy_sq)

        # Reach the closest target spot
        best_spot = None
        min_dist = inf

        for spot in target_spots:
            dist = manhattan_dist(self.memory.pos, spot)
            if spot in self.memory.arena and self.memory.arena[spot].type not in ["sea", "wall"] and dist < min_dist:
                min_dist = dist
                best_spot = spot
        
        # Move towards best spot
        # - If you are close enough to the enemy, you can try quick moves
        # quick = bool(max_dist(self.memory.pos, best_spot) <= 2)
        quick = False

        next_sq, _ = self.navigator.find_path(self.memory.pos, best_spot)
        action = self.motor.move_to(next_sq, quick=quick)

        return action