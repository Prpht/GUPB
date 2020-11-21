from gupb.controller.botelka_ml.wisdom import State
from gupb.model.characters import Action


def calculate_reward(old_state: State, new_state: State, old_action: Action) -> int:
    points = 0

    if old_state.health != new_state.health:
        # Lost health
        points -= 100

    if old_state.can_attack_enemy and old_action == Action.ATTACK:
        # Could attack enemy, and attacked enemy
        points += 120

    if old_state.can_attack_enemy and old_action != Action.ATTACK:
        # Could attack enemy, but didn't attack
        points -= 10

    if old_action == Action.ATTACK and not old_state.can_attack_enemy:
        # Could not attack enemy but attacked anyway, pointless move
        points -= 100

    if old_state.visible_enemies > 0:
        # Sees enemies, the more the better
        points += old_state.visible_enemies * 10

    if old_state.visible_enemies == 0:
        # No visible enemies
        points -= 25

    if old_state.tick > 120 and old_state.distance_to_menhir > 10:
        # Mist approaching
        points -= 50

    return points
