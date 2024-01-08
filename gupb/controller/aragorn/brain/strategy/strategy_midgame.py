from gupb.model import characters

from .strategy import Strategy



class StrategyMidgame(Strategy):
    def prepare_actions(self) -> characters.Action:
        self._clear_variables()

        yield self._prevent_idle_penalty()
        yield self._defend_from_attacks()
        yield self._pick_up_potion(8)
        yield self._attack_in_range()
        yield self._mist_forced_movement()
        yield self._pick_up_weapon(15)
        yield self._rotate_to_see_more()
        # yield self._attack_approach_sneaky()
        yield self._attack_approach_rage()
        yield self._attack_approach_normal()
        yield self._explore_the_map()
        yield self._spin()
