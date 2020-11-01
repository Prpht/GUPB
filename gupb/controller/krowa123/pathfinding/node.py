from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from gupb.model.coordinates import Coords


@dataclass
class Node:
    position: Coords
    parent: Optional[Node]
    g: int = 0  # Distance to start node
    h: int = 0  # Distance to goal node
    f: int = 0  # Total cost

    # Compare nodes
    def __eq__(self, other):
        return self.position == other.position

    # Sort nodes
    def __lt__(self, other):
        return self.f < other.f

    # Print node
    def __repr__(self):
        return f"({self.position},{self.f})"
