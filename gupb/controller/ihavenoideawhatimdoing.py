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
WEPON_REACH_BENEFIT: int = 0.7
# top left of map is 0 0
FALLOFF=12
INITIAL_ROTATE_DIAMETER = 1+20*2

def r(element, times):
    return [element] * times

def getRotateAround(diam):
    return {"clockwise": [
    [coordinates.Coords(0, -1), *r(coordinates.Coords(-1, 0),diam-2),
     coordinates.Coords(-1, 0)],
        *r([coordinates.Coords(0, -1), *r(coordinates.Coords(0, -1), diam - 2),
     coordinates.Coords(0, 1)],diam-2),
    [coordinates.Coords(1, 0), *r(coordinates.Coords(
        1, 0),diam-2), coordinates.Coords(0, 1)],
    ],
"counterclockwise": [
    [coordinates.Coords(1, 0), *r(coordinates.Coords(1, 0), diam - 2),
     coordinates.Coords(0, -1)],
    *r([coordinates.Coords(0, 1), *r(coordinates.Coords(0, -1), diam - 2),
        coordinates.Coords(0, -1)], diam - 2),
    [coordinates.Coords(0, 1), *r(coordinates.Coords(
        -1, 0), diam - 2), coordinates.Coords(-1, 0)],
],
    }



class IHaveNoIdeaWhatImDoingController:
    def __init__(self):
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()
        self.memory: dict[coordinates.Coords, tiles.TileDescription] = dict()
        self.time = 0
        self.heading_map = dict()
        self.weapon = weapons.Knife() # TODO
        self.decision_log = []
        self.position_log = []
        self.mist_distance = 0
        self.menhir_rotation = "counterclockwise"
        self.rotate_diam = INITIAL_ROTATE_DIAMETER

    def getTileGain(self, currentWeapon, newWeapon, dist):
        if(not newWeapon):
            return 0
        newReach = 1 if "reach" not in dir(
            newWeapon) else newWeapon.reach()  # cause still screw axe and amulets
        oldReach = 1 if "reach" not in dir(
            currentWeapon) else currentWeapon.reach()
        return (WEPON_REACH_BENEFIT # we want to promote weapons further from menhir
         * max(self.mist_distance // 20, 1) * (newReach - oldReach))

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
                "gain": vGain, "sourceDir": vSourceDir, "distance": vDist, "weapon": vWeapon }
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

    def canStepOn(self, coord: coordinates.Coords):
        return coord in self.arena.terrain and self.arena.terrain[coord].terrain_passable() and (not self.memory[coord] or not self.memory[coord][1].loot)

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
        return max(0,currentRadius - playerMenhirDist)

    def rotateFacingLeft(self, facing):
        if(facing[0] == 0 and facing[1] == 1):
            return coordinates.Coords(1, 0)
        if(facing[0] == 0 and facing[1] == -1):
            return coordinates.Coords(-1, 0)
        if(facing[0] == 1 and facing[1] == 0):
            return coordinates.Coords(0, -1)
        if(facing[0] == -1 and facing[1] == 0):
            return coordinates.Coords(0, 1)

    def getDiscoverOption(self, knowledge: characters.ChampionKnowledge):
        if(len(self.decision_log) < 3 or (self.decision_log[0] == "discover" and self.decision_log[1] == "discover")):
            return []
        if(self.decision_log[0]=="discover"):
            return [(1, [characters.Action.TURN_RIGHT, characters.Action.TURN_LEFT][(knowledge.position[0] + knowledge.position[1]+1) % 2], 'discover')]
        return [(0.1, [characters.Action.TURN_RIGHT, characters.Action.TURN_LEFT][(knowledge.position[0] + knowledge.position[1])%2],'discover')]

    def getNavOption(self, knowledge: characters.ChampionKnowledge):
        multiplier = 1 if self.getMistDistance(knowledge) > 8 else 1/2*(8 - self.getMistDistance(knowledge))
        preferedDir = self.mulitplyCoords(
            self.heading_map[knowledge.position]["sourceDir"],-1)
        if(preferedDir == None):
            return [(0.1*multiplier, characters.Action.TURN_RIGHT,"nav")]
        if(preferedDir == self.facing):
            return [(0.5*multiplier * self.getActionTime('nav_forward'), characters.Action.STEP_FORWARD, "nav_forward")]
        if(preferedDir == self.rotateFacingLeft(self.facing)):
            return [(0.6*multiplier, characters.Action.TURN_LEFT,"nav")]
        return [(0.6* multiplier, characters.Action.TURN_RIGHT, "nav")]

    def getObeliskCaptureOption(self, knowledge: characters.ChampionKnowledge):
        menhirOffset = (knowledge.position - self.menhir_position)
        rotateMap = getRotateAround(self.rotate_diam)[self.menhir_rotation]
        radiusShift = (self.rotate_diam - 1) // 2
        if(not (abs(menhirOffset[0]) <= radiusShift and abs(menhirOffset[1]) <= radiusShift) or self.mist_distance * 2 <= self.rotate_diam or self.heading_map[knowledge.position]["weapon"] != self.weapon):
            return []
        
        preferedDir = rotateMap[-menhirOffset[1] + radiusShift][menhirOffset[0] + radiusShift]
        if(self.mist_distance < 15):
            self.rotate_diam -= 2
        if(preferedDir == self.facing):
            if(self.canStepOn(knowledge.position + preferedDir)):
                return [(0.7, characters.Action.STEP_FORWARD, "capture")]
            else:
                self.menhir_rotation = "clockwise" if self.menhir_rotation == "counterclockwise" else "counterclockwise"
                # if(self.rotate_diam > 3 and self.mist_distance < 15):
                #     self.rotate_diam -= 2
                return [(0.7, characters.Action.TURN_RIGHT, "capture")]
        if(preferedDir == self.rotateFacingLeft(self.facing)):
            return [(0.7, characters.Action.TURN_LEFT, "capture")]
        return [(0.7, characters.Action.TURN_LEFT, "capture")]

    def getAttackOption(self, knowledge: characters.ChampionKnowledge):
        coords = [knowledge.position + self.mulitplyCoords(self.facing, x) for x in range(
            1, (1 if "reach" not in dir(self.weapon) else self.weapon.reach())+1)]
        for coord in coords:
            if(coord in self.arena.terrain and not self.arena.terrain[coord].terrain_transparent() or coord == self.menhir_position):
                return []
            if(coord in self.memory and self.memory[coord][1].character):
                return [(4 * self.getActionTime("attack"), characters.Action.ATTACK, "attack")]
        return []

    def getActionTime(self, name, percentageOfFalloff=FALLOFF):
        cTime = (percentageOfFalloff - len(list(filter(lambda x: x == name,
                                                       self.decision_log)))) / percentageOfFalloff
        return max(0,cTime)

    def getObtainOption(self, knowledge: characters.ChampionKnowledge):
        reach = (1 if "reach" not in dir(self.weapon) else self.weapon.reach())
        options = []
        for spread in [0,-1,1,-2,2]:
            for cDir in dirs:
                coords = [knowledge.position + self.mulitplyCoords(self.rotateFacingLeft(cDir), spread) + self.mulitplyCoords(cDir, x) for x in range(
                    1, reach + 1 + abs(spread))]
                for coord in coords:
                    if(coord in self.arena.terrain and not self.arena.terrain[coord].terrain_transparent() or coord == self.menhir_position):
                        break
                    if(coord in self.memory and self.memory[coord][1].character and self.memory[coord][1].character.controller_name != self.name):
                        action = characters.Action.TURN_LEFT if cDir == self.rotateFacingLeft(self.facing) else characters.Action.TURN_RIGHT
                        prio = reach / 50 * ((3 - abs(spread)) / 3)**2 * abs((self.time - self.memory[coord][0] + spread) / 5) * self.getActionTime("obtain", 4)
                        options.append((prio/2,action, "obtain"))
        return options

    def checkStuckOption(self, knowledge: characters.ChampionKnowledge):
        if(len(list(filter(lambda x: x != knowledge.position, self.position_log[-3:-1])))==0 and self.mist_distance > 4):
            if(self.getActionTime('nav_forward') == 0 or self.getActionTime('nav') == 0):
                return [(4 * self.getActionTime('checkStuck'), characters.Action.STEP_FORWARD if self.canStepOn(knowledge.position + self.facing) else characters.Action.TURN_RIGHT, 'checkStuck')]
        return []
                
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        decision = None
        self.updateTiles(knowledge)
        self.updateFacing(knowledge)
        if(knowledge.position not in self.heading_map or self.heading_map[knowledge.position]["distance"] > 2):
            self.computeHeadingMap()
        self.getMistDistance(knowledge)
        options = [*self.getNavOption(knowledge), *self.getAttackOption(
            knowledge), *self.getObtainOption(knowledge), *self.getObeliskCaptureOption(knowledge), *self.checkStuckOption(knowledge),*self.getDiscoverOption(knowledge)]
        decision = sorted(options, key=lambda option: -option[0])[0]
        self.position_log.append(knowledge.position)
        if(len(decision) > 2):
            self.decision_log.append(decision[2])
            if(len(self.decision_log) > FALLOFF):
                self.decision_log.pop(0)
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
