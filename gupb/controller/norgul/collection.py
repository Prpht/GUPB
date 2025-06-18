from gupb.controller.norgul.memory import Memory
from gupb.controller.norgul.misc import manhattan_dist
from gupb.controller.norgul.config import WEAPON_VALUES, POTION_VALUE, COLLECTION_BASE_FACTOR, COLLECTION_ENEMY_FACTOR

from gupb.model import characters
from gupb.model import coordinates
from gupb.model import weapons


# ---------------
# Collector class
# ---------------

# Represents Norgul's collecting skills
# - Picks up good weapons and potions
class Collector:

    def __init__(self, memory: Memory):
        self.memory = memory
    
    # ----------------------------------
    # Collector - search for best pickup
    # ----------------------------------

    def best_pickup(self) -> coordinates.Coords:
        ''' Returns coordinates of best pickup within current knowledge '''

        # For each pickup, we use a probabilistic formula to evaluate it's priority considering character's state
        max_priority = 0.0
        best_pickup = None

        # Consider weapons only if you don't have an axe
        if self.memory.weapon_name != "axe":
            curr_weapon_value = WEAPON_VALUES[self.memory.weapon_name]

            for sq, weapon in self.memory.arena.weapons.items():
                value_gain = WEAPON_VALUES[weapon.name] - curr_weapon_value

                # If we do not gain anything by picking up given weapon, we can skip following calculations
                if value_gain < 0:
                    continue

                our_dist = manhattan_dist(self.memory.pos, sq)

                priority = value_gain * COLLECTION_BASE_FACTOR * COLLECTION_ENEMY_FACTOR ** min(50, our_dist - 1)

                # Consider all enemies that are closer to given pickup than our character
                # - NOTE: This is unefficient, but since there are only 13 players at most, we can get away with that
                for e_sq, enemy in self.memory.arena.players.items():
                    enemy_dist = manhattan_dist(e_sq, sq)
                    if enemy_dist <= our_dist:
                        priority *= COLLECTION_ENEMY_FACTOR ** min(10, our_dist - enemy_dist + 1)
                
                if priority > max_priority:
                    max_priority = priority
                    best_pickup = sq
        
        # We always consider potions
        for sq in self.memory.arena.potions:
            our_dist = manhattan_dist(self.memory.pos, sq)

            priority = POTION_VALUE * COLLECTION_BASE_FACTOR * COLLECTION_ENEMY_FACTOR ** min(50, our_dist - 1)

            # We do the same as for weapons
            for e_sq, enemy in self.memory.arena.players.items():
                enemy_dist = manhattan_dist(e_sq, sq)
                if enemy_dist <= our_dist:
                    priority *= COLLECTION_ENEMY_FACTOR ** min(10, our_dist - enemy_dist + 1)
                
            if priority > max_priority:
                max_priority = priority
                best_pickup = sq
        
        return best_pickup
