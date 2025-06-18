from gupb.controller.norgul.memory import Memory
from gupb.controller.norgul.brain import Brain
from gupb.controller.norgul.misc import manhattan_dist

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

import traceback


class NorgulController(controller.Controller):
    Norgulium = "Norgulium"

    def __init__(norgul, first_name: str = "Norgul"):
        norgul.first_name: str = first_name

        # Norgul's memory
        norgul.memory = Memory()
        norgul.arena = None

        # Norgul's brain
        norgul.brain = Brain(norgul.memory)


    def __eq__(norgul, other: object) -> bool:
        if isinstance(other, NorgulController):
            return norgul.first_name == other.first_name
        return False


    def __hash__(norgul) -> int:
        return hash(norgul.first_name)


    def decide(norgul, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            # Step 1
            # - Update memory based on obtained knowledge
            norgul.memory.update(knowledge)

            # Step 2
            # - Decide about the next action
            action = norgul.brain.decide()

            # Step 4
            # - If target square (or set of squares) is already reached, rotate and gain more knowledge
            return action if action is not None else characters.Action.TURN_RIGHT
        except Exception as e:
            traceback.print_exc()


    def praise(norgul, score: int) -> None:
        pass


    def reset(norgul, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        norgul.memory.reset()

        arena_path = "resources/arenas/" + arena_description.name + ".gupb"
        norgul.memory.arena.load(arena_path)
        norgul.arena = arenas.Arena.load(arena_description.name)
        norgul.memory.terrain = norgul.arena.terrain
        norgul.memory.exploration.load(norgul.memory.arena)

    @property
    def name(norgul) -> str:
        return f'{norgul.first_name}'

    @property
    def preferred_tabard(norgul) -> characters.Tabard:
        return characters.Tabard.NORGUL


POTENTIAL_CONTROLLERS = [
    NorgulController("Norgul"),
]