
import gym

from gupb.controller.krowa123.big_brains.controller import LearnController
from gupb.controller.krowa123.big_brains.model import facing_encoder, weapon_encoder
from gupb.model.characters import Action, ChampionKnowledge
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

        self.action_space = spaces.Discrete(N_DISCRETE_ACTIONS)
        self.controller = LearnController("Learn")
        self.game = Game(arena_name=arena, to_spawn=[*self.config["controllers"], self.controller])
        self.game.cycle()
        self.champion = next(filter(lambda c: c.controller.name == self.controller.name, self.game.champions))

        self.observation_space = spaces.Box(low=0, high=5, shape=(SIZE, SIZE, 17), dtype=np.float32)

    def _get_state(self, knowledge: ChampionKnowledge, menhir_position):
        state = np.zeros(self.observation_space.shape, dtype=np.uint8)

        for coord, tile in self.game.arena.terrain.items():
            x, y = coord
            state[x, y, 0] = tile.terrain_passable()
            state[x, y, 1] = tile.terrain_transparent()
            state[x, y, 2] = any([isinstance(e, Mist) for e in tile.effects])

            if knowledge:
                if coord in knowledge.visible_tiles:
                    state[x, y, 3] = 1

                    character = knowledge.visible_tiles[coord].character
                    if character:
                        state[x, y, 4] = character.health
                        state[x, y, 5:9] = facing_encoder.transform([[character.facing.name]])[0]
                        state[x, y, 9:14] = weapon_encoder.transform([[character.weapon.name]])[0]

                    # loot = knowledge.visible_tiles[coord].loot
                    # if loot:
                    #     state[x, y, 7] = self.getWeapon(loot.name)

        xx, yy = self.champion.position
        state[xx, yy, 16] = 1
        xx, yy = menhir_position
        state[xx, yy, 15] = 1

        return state

    def _get_reward(self, last_position, last_health, healths):
        x, y = self.champion.position
        mx, my = self.controller.menhir_position
        # reward = x ** 2 + y ** 2 - 40
        reward = 26 - (mx - x) ** 2 + (my - y) ** 2

        if self._get_done():
            if not self.champion.alive:
                reward -= 200
            else:
                reward += 500
        # reward = 0
        #
        # if self.champion.alive:
        #     if self.game.finished:
        #         reward += 200
        #     else:
        #         reward += self.champion.health + len(self.game.deaths)
        #         if self.controller.next_action == Action.ATTACK:
        #             if sum(healths) <= sum([c.health for c in self.game.champions if c.controller.name != self.controller.name]):
        #                 reward -= 2
        #             else:
        #                 reward += 20
        #
        #         if self.controller.next_action == Action.STEP_FORWARD:
        #             if self.champion.position == last_position:
        #                 reward -= 2
        #
        #         reward -= (last_health - self.champion.health) * 10
        #
        # else:
        #     if len(self.game.deaths) == len(self.game.champions):
        #         reward -= 100
        #     else:
        #         reward -= 400

        return reward

    def _get_done(self):
        return (not self.champion.alive) or self.game.finished

    def step(self, action: int):
        last_health = self.champion.health
        last_position = self.champion.position
        healths = [c.health for c in self.game.champions if c.controller.name != self.controller.name]
        self.controller.next_action = list(Action)[action]

        self.cycle()

        return (
            self._get_state(self.controller.knowledge, self.controller.menhir_position),
            self._get_reward(last_position, last_health, healths),
            self._get_done(),
            {}
        )

    def reset(self, arena="mini"):
        self.controller = LearnController("Learn")
        self.game = Game(arena_name=arena, to_spawn=[*self.config["controllers"], self.controller])
        self.cycle()
        self.champion = next(filter(lambda c: c.controller.name == self.controller.name, self.game.champions))

        return self._get_state(self.controller.knowledge, self.controller.menhir_position)

    def cycle(self):
        while True:
            self.game.cycle()
            if self.game.current_state.name == 'InstantsTriggered' and not self.game.action_queue:
                self.game.cycle()
                break

    def render(self, mode='human'):
        print(self.controller.next_action)
        pass

    def close(self):
        pass
