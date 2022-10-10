from gupb.controller.aleph_aleph_zero.strategy import Strategy
from gupb.model import characters


class GuardingStrategy(Strategy):  # primitive guarding strategy that dodges the idle penalty
    TURN_AROUND = [characters.Action.TURN_LEFT]*2
    # PATROL = TURN_AROUND+[characters.Action.STEP_FORWARD]+TURN_AROUND+[characters.Action.STEP_FORWARD]+TURN_AROUND
    STAB_REPEATEDLY = [characters.Action.ATTACK]*(characters.PENALISED_IDLE_TIME-1)
    LOOK_TO_THE_SIDE = [characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
    PATROL_CYCLE = STAB_REPEATEDLY+LOOK_TO_THE_SIDE

    def __init__(self):
        self.action_queue = GuardingStrategy.TURN_AROUND

    def decide_and_proceed(self, knowledge, **kwargs):
        if len(self.action_queue)>0:
            action = self.action_queue.pop(0)
            return action, self
        else:
            self.action_queue += GuardingStrategy.PATROL_CYCLE
            return self.decide_and_proceed(knowledge)

