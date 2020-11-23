from gupb.controller.botelka_ml.models import Wisdom, MAX_HEALTH
from gupb.model.characters import Action


def calculate_reward(wisdom: Wisdom, prev_action: Action) -> int:
    """
    Calculates reward for given action, tries to tell if action makes sens.
    """
    points = 0

    points -= 100*(MAX_HEALTH-wisdom.bot_health) if wisdom.lost_health else 0
    points -= 30 if wisdom.reach_menhir_before_mist else 0

    if prev_action is Action.ATTACK:
        points -= 100 if not wisdom.can_attack_player else 0

    if prev_action is Action.TURN_LEFT:
        points -= 20 if wisdom.mist_visible else 0

    if prev_action is Action.TURN_RIGHT:
        points -= 20 if wisdom.mist_visible else 0

    if prev_action is Action.STEP_FORWARD:
        points += 10
        points += 50 if wisdom.enemies_visible else 0
        points += 50 if wisdom.better_weapon_visible else 0
        points -= 70 if wisdom.will_pick_up_worse_weapon else 0
        points -= 500 if wisdom.coords_did_not_change else 0

    return points
