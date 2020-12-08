
import gym
from sklearn.preprocessing import LabelEncoder

from gupb.controller.krowa123.big_brains.controller import AiController
from gupb.model.characters import Action, ChampionKnowledge, Facing
from gupb.model.effects import Mist
from gupb.model.games import Game
from gym import spaces
import numpy as np

N_DISCRETE_ACTIONS = len(Action) - 1

SIZE = 10


class Env(gym.Env):

    def __init__(self, config, arena="mini"):
        super(Env, self).__init__()
        self.config = config
        self.weapon_encoder = LabelEncoder()
        self.weapon_encoder.fit(["", "amulet", "axe", "bow", "knife", "sword"])

        self.action_space = spaces.Discrete(N_DISCRETE_ACTIONS)
        self.controller = AiController("Learn")
        self.game = Game(arena_name=arena, to_spawn=[*self.config["controllers"], self.controller])
        self.game.cycle()
        self.champion = next(filter(lambda c: c.controller.name == self.controller.name, self.game.champions))

        self.observation_space = spaces.Box(low=0, high=6, shape=(SIZE, SIZE, 7), dtype=np.uint8)

    def getFacing(self, facing: Facing):
        return {
            Facing.UP: 1,
            Facing.DOWN: 2,
            Facing.LEFT: 3,
            Facing.RIGHT: 4
        }[facing]

    def getWeapon(self, weapon: str):
        return {
            "amulet": 1,
            "axe": 2,
            "bow": 3,
            "knife": 4,
            "sword": 5
        }[weapon]

    def _get_state(self, knowledge: ChampionKnowledge, menhir_position):
        state = np.zeros((SIZE, SIZE, 7), dtype=np.uint8)

        for coord, tile in self.game.arena.terrain.items():
            x, y = coord
            state[x, y, 0] = 1 if tile.terrain_passable() else 0
            state[x, y, 1] = 1 if tile.terrain_transparent() else 0
            state[x, y, 2] = 1 if any([isinstance(e, Mist) for e in tile.effects]) else 0

            if knowledge:
                if coord in knowledge.visible_tiles:
                    state[x, y, 3] = 1

                    character = knowledge.visible_tiles[coord].character
                    if character and character.controller_name != self.controller.name:
                        # state[x, y, 4] = self.getFacing(character.facing)
                        state[x, y, 4] = character.health
                        # state[x, y, 6] = self.getWeapon(character.weapon.name)

                    # loot = knowledge.visible_tiles[coord].loot
                    # if loot:
                    #     state[x, y, 7] = self.getWeapon(loot.name)

        if knowledge:
            xx, yy = knowledge.position
            state[xx, yy, 6] = 1
        xx, yy = menhir_position
        state[xx, yy, 5] = 1

        return state

    def _get_reward(self, last_position, last_health, healths):
        reward = 0
        if self.champion.alive:
            if self.game.finished:
                reward += 200
            else:
                reward += self.champion.health + len(self.game.deaths)
                if self.controller.next_action == Action.ATTACK:
                    if sum(healths) <= sum([c.health for c in self.game.champions if c.controller.name != self.controller.name]):
                        reward -= 2
                    else:
                        reward += 20

                if self.controller.next_action == Action.STEP_FORWARD:
                    if self.champion.position == last_position:
                        reward -= 2

                reward -= (last_health - self.champion.health) * 10

        else:
            if len(self.game.deaths) == len(self.game.champions):
                reward -= 100
            else:
                reward -= 400

        return reward

    def _get_done(self):
        return (not self.champion.alive) or self.game.finished

    def step(self, action: int):
        last_health = self.champion.health
        last_position = self.champion.position
        healths = [c.health for c in self.game.champions if c.controller.name != self.controller.name]
        self.controller.next_action = list(Action)[action]

        cycle_done = False

        while not cycle_done:
            cycle_done = not self.game.action_queue
            self.game.cycle()

        return (
            self._get_state(self.controller.knowledge, self.controller.menhir_position),
            self._get_reward(last_position, last_health, healths),
            self._get_done(),
            {}
        )

    def reset(self, arena="mini"):
        self.controller = AiController("Learn")
        self.game = Game(arena_name=arena, to_spawn=[*self.config["controllers"], self.controller])
        self.game.cycle()
        self.champion = next(filter(lambda c: c.controller.name == self.controller.name, self.game.champions))

        return self._get_state(self.controller.knowledge, self.controller.menhir_position)

    def render(self, mode='human'):
        print(self.controller.next_action)
        pass

    def close(self):
        pass
