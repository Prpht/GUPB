from gupb.controller.norgul.arena_knowledge import ArenaKnowledge
from gupb.controller.norgul.exploration_knowledge import ExplorationKnowledge

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles


# -------------------
# Norgul memory class
# -------------------

# An abstraction for champion's memory
class Memory:
    
    def __init__(self):
        # Player state memory
        self.pos = None
        self.dir = None
        self.hp = None
        self.weapon_name = "knife"

        # Arena state memory
        self.arena = ArenaKnowledge()

        # Exploration memory
        self.exploration = ExplorationKnowledge()

        # Other things
        self.time = 0
        self.terrain = {}
    
    # ----------------------
    # Memory - static update
    # ----------------------

    def reset(self) -> None:
        self.pos = None
        self.dir = None
        self.hp = None
        self.weapon_name = "knife"

        self.arena.clear()
        self.exploration.areas.clear()

        self.time = 0
        self.terrain = {}
    
    # ----------------------
    # Memory - dynamic update
    # ----------------------

    def update(self, knowledge: characters.ChampionKnowledge) -> None:
        # Start by updating the time, since it affects other things such as ExplorationKnowledge
        self.time += 1

        self.pos = knowledge.position
        self.dir = knowledge.visible_tiles[self.pos].character.facing
        self.hp = knowledge.visible_tiles[self.pos].character.health
        self.weapon_name = knowledge.visible_tiles[self.pos].character.weapon.name

        self.arena.update(knowledge)
        self.exploration.update(knowledge, self.time)