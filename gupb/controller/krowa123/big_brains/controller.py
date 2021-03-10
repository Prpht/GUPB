import traceback

import numpy as np
from tensorflow.keras.models import load_model

from gupb.controller import Controller
from gupb.controller.krowa123.big_brains.model import facing_encoder, weapon_encoder
from gupb.model import characters, arenas, tiles
from gupb.model.arenas import Arena
from gupb.model.characters import ChampionKnowledge, Action
from gupb.model.effects import Mist


class LearnController(Controller):
    def __init__(self, uname):
        self.uname = uname
        self.knowledge = None
        self.menhir_position = None
        self.next_action = Action.DO_NOTHING

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET

    @property
    def name(self):
        return f"AiController_{self.uname}"

    def decide(self, knowledge: ChampionKnowledge):
        self.knowledge = knowledge
        return self.next_action

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_position = arena_description.menhir_position


class TestController(Controller):
    def __init__(self, uname, model_name):
        self.uname = uname
        self.menhir_position = None
        self.arena = None

        self.model = load_model(model_name)

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET

    @property
    def name(self):
        return f"Ai2Controller_{self.uname}"

    def _get_state(self, knowledge: ChampionKnowledge):
        state = np.zeros((10, 10, 17), dtype=np.uint8)

        for coord, tile in self.arena.terrain.items():
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

        if knowledge:
            xx, yy = knowledge.position
            state[xx, yy, 16] = 1
        xx, yy = self.menhir_position
        state[xx, yy, 15] = 1

        return state.reshape((-1, 10, 10, 17))

    def decide(self, knowledge: ChampionKnowledge):
        try:
            state = self._get_state(knowledge)
            action = np.argmax(self.model.predict(state))
            action = list(Action)[action]
            print(action)
            return action
        except Exception as e:
            traceback.print_exc()
        return Action.DO_NOTHING

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_position = arena_description.menhir_position
        self.arena = Arena.load(arena_description.name)
        self.arena.menhir_position = self.menhir_position
        self.arena.terrain[self.menhir_position] = tiles.Menhir()
