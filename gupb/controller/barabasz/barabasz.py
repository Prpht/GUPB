import random

from gupb import controller
from gupb.model import arenas, coordinates, weapons
from gupb.model import characters
from gupb.controller.barabasz.weapon_mechanics import deathzone

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
]


WEAPONS = {
    'knife': weapons.Knife,
    'sword': weapons.Sword,
    'bow': weapons.Bow,
    'axe': weapons.Axe,
    'amulet': weapons.Amulet
}


def weapon_description_to_weapon(description: weapons.WeaponDescription):
    if description.name[0:3] == 'bow':
        weapon = weapons.Bow()
        if description.name == 'bow_loaded':
            weapon.ready = True
    else:
        weapon = WEAPONS[description.name]()

    return weapon


class BarabaszController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.position: coordinates.Coords = None
        self.weapon: weapons.Weapon = weapons.Knife()
        self.health: int = 8
        self.facing: characters.Facing = characters.Facing.random()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BarabaszController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:

        self.update_self_knowledge(knowledge)

        # Check position, check which side one is facing, check tile description
        in_front = coordinates.add_coords(knowledge.position, self.facing.value)

        if in_front in knowledge.visible_tiles.keys():
            if knowledge.visible_tiles[in_front].type == "wall" or knowledge.visible_tiles[in_front].type == "sea":
                return characters.Action.TURN_LEFT
            if isinstance(self.weapon, weapons.Bow) and not self.weapon.ready:
                return characters.Action.ATTACK
            deathtiles = deathzone(weapon=self.weapon,
                                   position=self.position,
                                   facing=self.facing.value)
            for cords in deathtiles:
                if cords in knowledge.visible_tiles.keys() and knowledge.visible_tiles[cords].character:
                    # print("SMACK! ", self.weapon)
                    # print("Position: ", knowledge.position, "EnemyPos: ", cords)
                    return characters.Action.ATTACK

        weighted_random = random.choices(POSSIBLE_ACTIONS, weights=(1, 1, 3))[0]
        return weighted_random

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE

    def update_self_knowledge(self, knowledge: characters.ChampionKnowledge = None):
        self.position = knowledge.position
        tile = knowledge.visible_tiles.get(self.position)
        character = tile.character if tile else None

        if character:
            self.weapon = weapon_description_to_weapon(character.weapon)
            self.health = character.health
            self.facing = character.facing
