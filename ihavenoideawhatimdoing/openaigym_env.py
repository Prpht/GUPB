from gupb.controller import ihavenoideawhatimdoing
import gym
from gupb.model import characters
from gupb.model.characters import Action, ChampionKnowledge
from gupb.model.games import Game
from gupb.model import weapons, arenas
from gym import spaces
import numpy as np
from gupb.default_config import CONFIGURATION
from gupb.controller.ihavenoideawhatimdoing import IHaveNoIdeaWhatImDoingController
N_DISCRETE_ACTIONS = len(Action)

ARENA_NAMES = ['archipelago', 'dungeon', 'fisher_island', 'wasteland', 'island', 'mini']

SIZE = 7


# class MyController():
#     def __init__(self):
#         self.knowledge = None
#         self.menhir_position = None
#     @property
#     def preferred_tabard(self) -> characters.Tabard:
#         return characters.Tabard.RED
#     @property
#     def name(self):
#         return "MyController"
#     def decide(self, knowledge: ChampionKnowledge):
#         self.knowledge = knowledge
#         return self.next_action
#     def reset(self, arena_description: arenas.ArenaDescription) -> None:
#         self.menhir_position = arena_description.menhir_position

class GameEnv(gym.Env):
#   metadata = {'render.modes': ['human']}

    def getWeaponFromDesc(self, weapon: weapons.WeaponDescription):
        if not weapon:
            return 0
        return {
            "amulet": 1,
            "axe": 2,
            "knife": 3,
            "sword":4,
            "bow": 5
        }[weapon.name]
    def getWeaponFromWeapon(self, weapon: weapons.Weapon):
        if not weapon:
            return 0
        return {
            "Amulet": 1,
            "Axe": 2,
            "Knife": 3,
            "Sword":4,
            "Bow": 5
        }[type(weapon).__name__]

    def __init__(self, arena="archipelago"):
        super(GameEnv, self).__init__()
        self.action_space = spaces.Discrete(N_DISCRETE_ACTIONS)
        self.controller = IHaveNoIdeaWhatImDoingController()
        self.game = Game(arena_name=arena,to_spawn=[*CONFIGURATION["controllers"],self.controller])
        self.observation_space = spaces.Box(low=0, high=5,
                                            shape=(SIZE,SIZE,5), dtype=np.uint8)
    def get_obs(self, knowledge: ChampionKnowledge, menhir_position):
        new_space = np.zeros((SIZE,SIZE,5), dtype=np.uint8)
        for coords,tile in self.game.arena.terrain.items():
            if knowledge:
                dist = (knowledge.position - coords)
                x = abs(dist[0])+SIZE//2
                y = abs(dist[1])+SIZE//2
                if(x < SIZE//2 and y < SIZE//2):
                    new_space[x,y,0] = 1 if tile.terrain_passable() else 0
                    new_space[x,y,1] = 1 if tile.terrain_transparent() else 0
                    if coords in knowledge.visible_tiles:
                        new_space[x,y,2] = 1 if knowledge.visible_tiles[coords].character else 0
        return new_space

    def step(self, action):
        self.controller.next_action = list(Action)[action]
        self.game.cycle()
        mycontrollers = list(filter(lambda x: x.controller.name == "IHaveNoIdeaWhatImDoingController",self.game.champions))
        if len(mycontrollers) > 0:
            me = mycontrollers[0]
        killed = 1+len(list(filter(lambda x: not x.alive,self.game.champions)))
        return self.get_obs(self.controller.knowledge, self.controller.menhir_position), killed if (len(mycontrollers) and me.alive) else 0, not (len(mycontrollers) and me.alive), {}
    def reset(self, arena="archipelago"):
        self.controller = IHaveNoIdeaWhatImDoingController()
        self.game = Game(arena_name=arena,to_spawn=[*CONFIGURATION["controllers"],self.controller])
        return self.get_obs(self.controller.knowledge, self.controller.menhir_position)

    def render(self, mode='human'):
        pass
    def close(self):
        pass
