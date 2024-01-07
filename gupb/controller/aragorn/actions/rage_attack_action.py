from gupb.model.coordinates import *
from gupb.model.profiling import profile

from .action import Action
from .attack_closest_enemy_action import AttackClosestEnemyAction
from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import DEBUG, DEBUG2, INFINITY
from gupb.controller.aragorn import utils



class RageAttackAction(AttackClosestEnemyAction):
    HAPPY_NEW_YEAR = [
        # 53254780140597,
        # 16210931983372679264624916789,
        
        47403228639173111709310103423398415522718923899712,
        912483974970427094311,
        14461117651760316,
        # 947871564346996264452,
    ]
    rage_attack_bots = None

    def __init__(self) -> None:
        super().__init__()
        
        if RageAttackAction.rage_attack_bots is None:
            RageAttackAction.rage_attack_bots = [
                self.d(x, 32378946584) for x in self.HAPPY_NEW_YEAR
            ]
    
    def d(self, int_to_decrypt, key):
        ints = []
        while int_to_decrypt > 0:
            ints.append(int_to_decrypt & 0xff)
            int_to_decrypt >>= 8
        ints.reverse()

        seed = key

        def rc():
            nonlocal seed
            seed = (seed * 1103515245 + 12345) & 0x7fffffff
            return seed
        
        ret = ""

        for i in ints:
            ret += chr(i ^ (rc() % 255))

        return ret

    def getClosestEnemy(self, memory: Memory):
        # GET CLOSEST ENEMY
        closestEnemy = None
        closestEnemyDistance = INFINITY

        if DEBUG2: print("[ARAGORN|RAGE_ATTACK_ENEMY] Searching for closest enemy")

        for coords in memory.map.terrain:
            if (
                # tile has character
                memory.map.terrain[coords].character is not None
                # ignore if data is outdated
                # and (not hasattr(memory.map.terrain[coords], 'tick') or memory.map.terrain[coords].tick >= memory.tick - self.OUTDATED_DATA_TICKS)
                # ignore ourselfs
                # and memory.map.terrain[coords].character.controller_name != OUR_BOT_NAME
                # ignore our position
                and memory.position != coords
                # ignore enemies with greater health
                # and memory.map.terrain[coords].character.health <= memory.health
                # ignore enemies with health greater than reward of killing (potion restore)
                # and memory.map.terrain[coords].character.health <= consumables.POTION_RESTORED_HP

                and memory.map.terrain[coords].character.controller_name in RageAttackAction.rage_attack_bots
            ):
                distance = utils.manhattanDistance(memory.position, coords)
                
                if distance < closestEnemyDistance:
                    closestEnemy = coords
                    closestEnemyDistance = distance
        
        if closestEnemy is None:
            if DEBUG2: print("[ARAGORN|RAGE_ATTACK_ENEMY] No closest enemy found")
            return None, INFINITY
        
        if DEBUG2: print("[ARAGORN|RAGE_ATTACK_ENEMY] Closest enemy found at", closestEnemy, "with distance", closestEnemyDistance)
        
        return closestEnemy, closestEnemyDistance
    
    @profile
    def perform(self, memory: Memory) -> Action:
        closestEnemy, closestEnemyDistance = self.getClosestEnemy(memory)
        
        if closestEnemy is None:
            return None
        
        return self.approachEnemy(memory, closestEnemy, closestEnemyDistance)
