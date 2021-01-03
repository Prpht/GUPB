from typing import List

from gupb.controller.krowa123.competetive_self_play.controller import \
    AIController
from gupb.model.characters import Action
from gupb.model.games import Game


class Environment:

    def __init__(
        self,
        agents_number: int
    ):
        self.__controllers = [AIController(uname=f"{i}" for i in range(agents_number))]
        self.__game = Game(
            arena_name="dungeon_mini",
            to_spawn=self.__controllers
        )
        self.__game.cycle()
        self.__champions = self.__game.champions

    def step(self, actions: List[int]) -> List[tuple]:
        result = []
        for i in range(len(actions)):
            self.__step_for_controller(
                self.__controllers[i],
                actions[i]
            )
        self.__game.cycle()
        for i in range(len(actions)):
            result.append(self.__prepare_controller_result(i))
        return result

    def reset(self):
        pass

    def render(self, mode='human'):
        pass

    def cycle(self):
        while True:
            self.__game.cycle()
            if self.__game.current_state.name == 'InstantsTriggered' and not self.game.action_queue:
                self.__game.cycle()
                break

    def __step_for_controller(
        self,
        controller: AIController,
        action: int
    ) -> None:
        controller.next_action = list(Action)[action]

    def __prepare_controller_result(self, controller_idx: int) -> tuple:
        pass
