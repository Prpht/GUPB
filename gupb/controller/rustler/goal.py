from typing_extensions import override
from gupb.model import characters, coordinates
from dataclasses import dataclass


@dataclass(slots=True, eq=False)
class Goal:
    name: str
    priority: float
    journey_target: coordinates.Coords
    vanishable: bool
    facing: characters.Facing
    wandering: int

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Goal):
            return False

        return (
            self.name == other.name
            and self.priority == other.priority
            and self.journey_target == other.journey_target
        )

    @override
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

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Goal):
            return False

        return self.priority < other.priority
