from gupb.model import characters, coordinates


class Goal:
    def __init__(
        self,
        name: str,
        priority: float,
        target_cords: coordinates.Coords,
        vanishable: bool = False,
        facing: characters.Facing = None,
        wandering: int = 0,
    ):
        self.name = name
        self.priority = priority
        self.journey_target = target_cords
        self.vanishable = (
            vanishable  # True if the goal should be deleted when stepped on
        )
        self.facing = facing
        self.wandering = wandering

    def __eq__(self, other):
        if isinstance(other, Goal):
            return (
                self.name == other.name
                and self.priority == other.priority
                and self.journey_target == other.journey_target
                and self.vanishable == other.vanishable
                and self.facing == other.facing
                and self.wandering == other.wandering
            )
        return False

    def __hash__(self):
        return hash(
            (
                self.name,
                self.priority,
                self.journey_target,
                self.vanishable,
                self.facing,
                self.wandering,
            )
        )

    def __lt__(self, other):
        return self.priority < other.priority
