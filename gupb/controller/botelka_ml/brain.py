import json
import random
from collections import defaultdict
from typing import Tuple, Dict

from gupb.controller.botelka_ml.models import Wisdom
from gupb.model.characters import Action
from pathlib import Path

EPS = 0.05

POSSIBLE_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]

ALPHA = 0.05
DECAY = 0.005
GAMMA = 0.9


def init_q() -> Dict:
    path = Path(__file__).parent.absolute().joinpath("botelka_q.dump")

    if not path.exists():
        return defaultdict(int)

    with open(path, "r") as file:
        q = {(tuple(obj[0][0]), str_to_action(obj[0][1])): obj[1] for obj in json.loads(file.read())}
        q = defaultdict(int, q)

    return q


def save_q(q: Dict):
    path = Path(__file__).parent.absolute().joinpath("botelka_q.dump")

    with open(path, "w") as f:
        f.write(json.dumps(
            [
                [[list(key[0]), action_to_str(key[1])], value]
                for key, value in q.items()
            ]
        ))


def epsilon_greedy_action(q, state) -> Action:
    if random.random() < EPS:
        return random.choice(POSSIBLE_ACTIONS)

    values = {q[state, action]: action for action in POSSIBLE_ACTIONS}
    return values[max(values)]


def get_state(wisdom: Wisdom) -> Tuple[int, int, int, int]:
    return (
        int(wisdom.can_attack_player), int(wisdom.mist_visible), int(wisdom.better_weapon_visible),
        int(wisdom.distance_to_menhir)
    )


def action_to_str(action: Action) -> str:
    return {
        Action.TURN_RIGHT: "right",
        Action.TURN_LEFT: "left",
        Action.STEP_FORWARD: "forward",
        Action.DO_NOTHING: "nothing",
        Action.ATTACK: "attack"
    }[action]


def str_to_action(action: str) -> Action:
    return {
        "right": Action.TURN_RIGHT,
        "left": Action.TURN_LEFT,
        "forward": Action.STEP_FORWARD,
        "nothing": Action.DO_NOTHING,
        "attack": Action.ATTACK
    }[action]
