from gupb.model import characters

from .strategy import Strategy



class StrategyEndgame(Strategy):
    def prepare_actions(self) -> characters.Action:
        yield self._prevent_idle_penalty()
        yield self._defend_from_attacks()
        yield self._pick_up_potion(5)
        yield self._attack_in_range()
        yield self._conquer_menhir()
        yield self._pick_up_weapon(3)
        yield self._rotate_to_see_more()
        # yield self._attack_approach_sneaky()
        # yield self._attack_approach_rage()
        yield self._attack_approach_normal()
        yield self._spin()
