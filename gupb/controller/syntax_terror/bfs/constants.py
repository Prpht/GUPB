from gupb.model import characters, coordinates

PASSABLE_TILE_TYPES = frozenset({"land", "forest", "menhir"})
LOS_TRANSPARENT_TYPES = frozenset({"land", "sea", "menhir"})

FACINGS = (
    characters.Facing.UP,
    characters.Facing.RIGHT,
    characters.Facing.DOWN,
    characters.Facing.LEFT,
)

State = tuple[coordinates.Coords, characters.Facing]

_TURN_COST = 1
_STEP_BASE_COST = 1
_INF = float("inf")

_FORWARD_ONLY = (
    (characters.Action.STEP_FORWARD, "forward"),
)

_OMNI_STEPS = (
    (characters.Action.STEP_FORWARD, "forward"),
    (characters.Action.STEP_BACKWARD, "opposite"),
    (characters.Action.STEP_LEFT, "turn_left"),
    (characters.Action.STEP_RIGHT, "turn_right"),
)
