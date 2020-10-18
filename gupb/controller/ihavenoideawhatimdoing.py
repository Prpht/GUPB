from queue import SimpleQueue

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import weapons
from gupb.model import tiles
# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic

dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
MIST_TTH: int = 5
WEPON_REACH_BENEFIT: int = 2
# top left of map is 0 0
FALLOFF=5

class IHaveNoIdeaWhatImDoingController:
    def __init__(self):
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()
        self.memory: dict[coordinates.Coords, tiles.TileDescription] = dict()
        self.time = 0
        self.heading_map = dict()
        self.weapon = weapons.Knife() # TODO
        self.decision_log = []
        self.mist_distance = 0

    def getTileGain(self, currentWeapon, newWeapon, dist):
        if(not newWeapon):
            return 0
        newReach = 1 if "reach" not in dir(
            newWeapon) else newWeapon.reach()  # cause screw axe and amulets
        oldReach = 1 if "reach" not in dir(
            currentWeapon) else currentWeapon.reach()
        return (WEPON_REACH_BENEFIT * max(self.mist_distance // 20, 1) * (newReach - oldReach))

    def getWeaponFromLoot(self, weapon: weapons.WeaponDescription):
        if not weapon:
            return None
        return {
            "axe": weapons.Axe(),
            "sword":weapons.Sword(),
            "amulet": weapons.Amulet(),
            "knife": weapons.Knife(),
            "bow": weapons.Bow()
        }[weapon.name]

    def computeHeadingMap(self):
        queue = []
        del self.heading_map
        self.heading_map = dict()
        queue.append(
            (self.menhir_position, 0, 0, None, self.weapon))
        while(queue):
            vPos, vGain, vDist, vSourceDir, vWeapon = queue.pop(0)
            if(vPos not in self.arena.terrain):
                continue
            if(vPos in self.heading_map and vGain <= self.heading_map[vPos]["gain"]):
                continue
            if(not self.arena.terrain[vPos].terrain_passable()):
                continue
            self.heading_map[vPos] = {
                "gain": vGain, "sourceDir": vSourceDir, "distance": vDist }
            newWeapon = (None if vPos not in self.memory else self.getWeaponFromLoot(self.memory[vPos][1].loot)) or self.arena.terrain[vPos].loot
            for cDir in dirs:
                queue.append((
                    vPos + coordinates.Coords(*cDir), vGain - 1 + self.getTileGain(vWeapon, newWeapon, vDist), vDist + 1, cDir if vDist > 0 else None, newWeapon or vWeapon))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, IHaveNoIdeaWhatImDoingController):
            return True
        return False

    def __hash__(self) -> int:
        return 42

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_position = arena_description.menhir_position
        # we're just using the static method to avoid repeating parsing files
        self.arena = arenas.Arena.load(arena_description.name)
        pass

    def mulitplyCoords(self, coords, val):
        if coords is None:
            return None
        return coordinates.Coords(coords[0] * val, coords[1] * val)

    def getMistDistance(self, knowledge: characters.ChampionKnowledge):
        currentRadius = self.arena.mist_radius - (self.time // MIST_TTH)
        playerMenhirDist = self.heading_map[knowledge.position]["distance"]
        self.mist_distance = currentRadius - playerMenhirDist
        return currentRadius - playerMenhirDist

    def rotateFacingLeft(self, facing):
        if(facing[0] == 0 and facing[1] == 1):
            return coordinates.Coords(1, 0)
        if(facing[0] == 0 and facing[1] == -1):
            return coordinates.Coords(-1, 0)
        if(facing[0] == 1 and facing[1] == 0):
            return coordinates.Coords(0, -1)
        if(facing[0] == -1 and facing[1] == 0):
            return coordinates.Coords(0, 1)

    def getNavOption(self, knowledge: characters.ChampionKnowledge):
        preferedDir = self.mulitplyCoords(
            self.heading_map[knowledge.position]["sourceDir"],-1)
        if(preferedDir == None):
            return [(0.1, characters.Action.TURN_RIGHT)]
        if(preferedDir == self.facing):
            return [(0.5, characters.Action.STEP_FORWARD)]
        if(preferedDir == self.rotateFacingLeft(self.facing)):
            return [(0.7, characters.Action.TURN_LEFT)]
        return [(0.7, characters.Action.TURN_RIGHT)]

    def getAttackOption(self, knowledge: characters.ChampionKnowledge):
        coords = [knowledge.position + self.mulitplyCoords(self.facing, x) for x in range(
            1, (1 if "reach" not in dir(self.weapon) else self.weapon.reach())+1)]
        for coord in coords:
            if(coord in self.arena.terrain and not self.arena.terrain[coord].terrain_transparent()):
                return []
            if(coord in self.memory and self.memory[coord][1].character):
                return [(4, characters.Action.ATTACK, "attack")]
        return []


    def getActionTime(self, name):
        return (FALLOFF - len(list(filter(lambda x: x == name, self.decision_log)))) / FALLOFF

    def getObtainOption(self, knowledge: characters.ChampionKnowledge):
        neededDir = None
        reach = (1 if "reach" not in dir(self.weapon) else self.weapon.reach())
        for cDir in dirs:
            coords = [knowledge.position + self.mulitplyCoords(cDir, x) for x in range(
                1, reach + 1)]
            for coord in coords:
                if(coord in self.arena.terrain and not self.arena.terrain[coord].terrain_transparent()):
                    break
                if(coord in self.memory and self.memory[coord][1].character and self.memory[coord][1].character.controller_name != self.name):
                    neededDir = cDir # we should avoid walking into characters but let's skip it xd
        if not neededDir:
            return []
        if(neededDir == self.rotateFacingLeft(self.facing)):
            return [(2 * reach/50 * self.getActionTime("obtain"), characters.Action.TURN_LEFT, "obtain")] # bow reach
        return [(2 * reach / 50 * self.getActionTime("obtain"), characters.Action.TURN_RIGHT, "obtain")]
                
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        decision = None
        self.updateTiles(knowledge)
        if(knowledge.position not in self.heading_map or self.heading_map[knowledge.position]["distance"] > 2):
            self.computeHeadingMap()
        self.updateFacing(knowledge)

        options = [*self.getNavOption(knowledge), *self.getAttackOption(knowledge), *self.getObtainOption(knowledge)]
        decision = sorted(options, key=lambda option: -option[0])[0]
        if(2 in decision):
            self.decision_log.append(decision[2])
            if(len(self.decision_log) > FALLOFF):
                self.decision_log.pop()
        if(decision[1] is characters.Action.STEP_FORWARD):
            self.pickupWeapon(knowledge, self.facing)
        self.time += 1
        return decision[1]

    def pickupWeapon(self, knowledge, facing):
        if(self.getWeaponFromLoot(self.memory[knowledge.position + facing][1].loot)):
            self.weapon = self.getWeaponFromLoot(
                self.memory[knowledge.position + facing][1].loot)
    @property
    def name(self) -> str:
        return 'IHaveNoIdeaWhatImDoingController'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED

    def updateFacing(self, knowledge: characters.ChampionKnowledge):
        for dir in dirs:
            if(knowledge.position + dir in knowledge.visible_tiles):
                self.facing = dir
                return

    def updateTiles(self, knowledge: characters.ChampionKnowledge):
        for coords in knowledge.visible_tiles:
            self.memory[coords] = (self.time, knowledge.visible_tiles[coords])


POTENTIAL_CONTROLLERS = [
    IHaveNoIdeaWhatImDoingController(),
]
