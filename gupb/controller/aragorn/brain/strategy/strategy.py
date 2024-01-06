from gupb.model import characters
from gupb.controller.aragorn.actions import *


class Strategy:
    def prepare_actions(self, brain: 'Brain') -> characters.Action:
        action = AdvancedExploreAction()
        yield action, "Exploring"
