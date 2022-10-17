from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.controller.lord_icon.strategies.core import Strategy
from gupb.model.characters import Action


class ExploreStrategy(Strategy):
    name = "ExploreStrategy"

    @staticmethod
    def get_action(knowledge: Knowledge):
        return Action.TURN_LEFT

            
            

