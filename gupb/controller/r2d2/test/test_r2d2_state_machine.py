import pytest
from statemachine import StateMachine, State
from statemachine.exceptions import TransitionNotAllowed

from gupb.controller.r2d2.r2d2_state_machine import R2D2StateMachineV2


def test_stage_I():

    # Initialize state machine
    r2d2_state_machine = R2D2StateMachineV2()
    assert r2d2_state_machine.current_state == r2d2_state_machine.st1_choose_destination

    # choose destination
    r2d2_state_machine.st1_destination_chosen()
    assert r2d2_state_machine.current_state == r2d2_state_machine.st1_approach_destination

    # reach destination
    r2d2_state_machine.st1_destination_reached()
    assert r2d2_state_machine.current_state == r2d2_state_machine.st1_choose_destination

    # choose destination, approach and find weapon
    r2d2_state_machine.st1_destination_chosen()
    r2d2_state_machine.st1_weapon_localized()
    assert r2d2_state_machine.current_state == r2d2_state_machine.st1_approach_weapon

    # lose weapon
    r2d2_state_machine.st1_weapon_lost()
    assert r2d2_state_machine.current_state == r2d2_state_machine.st1_choose_destination

    # choose destination, approach and collect weapon
    r2d2_state_machine.st1_destination_chosen()
    r2d2_state_machine.st1_weapon_localized()
    r2d2_state_machine.st1_weapon_collected()
    assert r2d2_state_machine.current_state == r2d2_state_machine.st2_choose_destination


def test_stage_I_illegal_transition():

    # Initialize state machine, choose destination and localize weapon
    r2d2_state_machine = R2D2StateMachineV2()
    r2d2_state_machine.st1_destination_chosen()
    r2d2_state_machine.st1_weapon_localized()

    # Try transition "destination_reached()", which is not allowed from state "st1_approach_weapon"
    try:
        r2d2_state_machine.st1_destination_reached()
    except Exception as e:
        assert isinstance(e, TransitionNotAllowed)
    assert r2d2_state_machine.current_state == r2d2_state_machine.st1_approach_weapon

    # Try transition "weapon_localized()", which is not allowed from state "st1_approach_weapon"
    try:
        r2d2_state_machine.st1_weapon_localized()
    except Exception as e:
        assert isinstance(e, TransitionNotAllowed)
    assert r2d2_state_machine.current_state == r2d2_state_machine.st1_approach_weapon

    # Try transition "destination_chosen()", which is not allowed from state "st1_approach_weapon"
    try:
        r2d2_state_machine.st1_destination_chosen()
    except Exception as e:
        assert isinstance(e, TransitionNotAllowed)
    assert r2d2_state_machine.current_state == r2d2_state_machine.st1_approach_weapon

    # Colect weapon and move to stage II
    r2d2_state_machine.st1_weapon_collected()
    assert r2d2_state_machine.current_state == r2d2_state_machine.st2_choose_destination


def test_stage_II():
    # TODO: implement test case
    pass


def test_stage_III():
    # TODO: implement test case
    pass
