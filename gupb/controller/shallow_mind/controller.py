from gupb.controller.shallow_mind.arenna_wrapper import ArenaWrapper
from gupb.controller.shallow_mind.consts import WEAPONS_PRIORITY
from gupb.controller.shallow_mind.utils import get_first_possible_move
from gupb.model import characters
from gupb.model.arenas import ArenaDescription
from gupb.model.characters import ChampionDescription, Action, ChampionKnowledge
from queue import SimpleQueue


class ShallowMindController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.arena: ArenaWrapper = None
        self.action_queue: SimpleQueue[Action] = SimpleQueue()
        self.bow_taken = False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ShallowMindController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: ArenaDescription) -> None:
        self.arena = ArenaWrapper(arena_description)
        self.bow_taken = False

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        self.arena.prepare_matrix(knowledge)
        if not self.action_queue.empty():
            return self.action_queue.get()
        champ = self.arena.champion
        if self.arena.can_hit:
            return Action.ATTACK
        if self.arena.prev_champion:
            if champ.health != self.arena.prev_champion.health:
                action = self.arena.find_escape_action()
                if action != Action.DO_NOTHING:
                    self.action_queue.put(Action.STEP_FORWARD)
                    return action
        if self.arena.calc_mist_dist() > 5:
            if champ.weapon != WEAPONS_PRIORITY[0]:
                action, _ = self.arena.find_move_to_nearest_weapon(WEAPONS_PRIORITY[0])
                if action != Action.DO_NOTHING:
                    return action
                elif champ.weapon == WEAPONS_PRIORITY[-1]:
                    weapons = [self.arena.find_move_to_nearest_weapon(weapon) for weapon in WEAPONS_PRIORITY]
                    action, _ = get_first_possible_move(weapons)
                    if action != Action.DO_NOTHING:
                        return action
        # todo this need to be redone
        action, length = self.arena.find_move_to_menhir()
        if action == Action.DO_NOTHING:
            return self.arena.find_scan_action()
        return action

    @property
    def name(self) -> str:
        return f'ShallowMindController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.GREY


POTENTIAL_CONTROLLERS = [
    ShallowMindController('test'),
]
