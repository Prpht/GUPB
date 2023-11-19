from statemachine import StateMachine, State
from dataclasses import dataclass

@dataclass(unsafe_hash=True)
class R2D2StateValue:
    name: str
    stage: int
    description: str

R2D2StateValue("SearchingForMenhir", 1, "None")

class R2D2StateMachine(StateMachine):

    # Define states
    # - Stage I (Find Weapons)
    st1_choose_destination = State('ChooseDestinationStI', value=R2D2StateValue(
        name="ChooseDestinationStI", stage=1, description=""
    ), initial=True)
    st1_approach_destination = State('ApproachDestinationStI', value=R2D2StateValue(
        name="ApproachDestinationStI", stage=1, description=""
    ))
    st1_approach_weapon = State('ApproachWeaponStI', value=R2D2StateValue(
        name="ApproachWeaponStI", stage=1, description=""
    ))

    # - Stage II (Find Menhir)
    st2_choose_destination = State('ChooseDestinationStII', value=R2D2StateValue(
        name="ChooseDestinationStII", stage=2, description=""
    ))
    st2_approach_destination = State('ApproachDestinationStII', value=R2D2StateValue(
        name="ApproachDestinationStII", stage=2, description=""
    ))
    st2_approach_menhir = State('ApproachMenhirStII', value=R2D2StateValue(
        name="ApproachMenhirStII", stage=2, description=""
    ))

    # - Stage III (Defend Menhir)
    st3_choose_destination = State('ChooseDestinationStIII', value=R2D2StateValue(
        name="ChooseDestinationStIII", stage=3, description=""
    ))
    st3_approach_destination = State('ApproachDestinationStIII', value=R2D2StateValue(
        name="ApproachDestinationStIII", stage=3, description=""
    ))

    # st4_runaway = State('RunawayStIV', value=R2D2StateValue(
    #     name="Runaway", stage=4, description=""
    # ))

    # Define transitions
    # - Stage I (Find Weapons)
    st1_destination_chosen = st1_choose_destination.to(st1_approach_destination)
    st1_destination_reached = st1_approach_destination.to(st1_choose_destination)
    st1_weapon_localized = st1_approach_destination.to(st1_approach_weapon)
    st1_weapon_lost = st1_approach_weapon.to(st1_choose_destination)
    st1_weapon_collected = st1_approach_weapon.to(st2_choose_destination)

    # - Stage II (Find Menhir)
    st2_destination_chosen = st2_choose_destination.to(st2_approach_destination)
    st2_destination_reached = st2_approach_destination.to(st2_choose_destination)
    st2_menhir_localized = st2_approach_destination.to(st2_approach_menhir)
    st2_menhir_reached = st2_approach_menhir.to(st3_choose_destination)

    # - Stage III (Defend Menhir)
    st3_destination_chosen = st3_choose_destination.to(st3_approach_destination)
    st3_destination_reached = st3_approach_destination.to(st3_choose_destination)

    # - Stage IV (Runaway)
    # st4_runaway = st3_choose_destination.to(st4_runaway)