import enum
from gupb.model import characters
from typing import List, Optional, Dict, Tuple
from gupb.model import coordinates
from gupb.controller.tuptus.map import Map

import heapq

"""
    @ TODO:
        1) Add types

"""

class Pathfinder():
    def __init__(self, current_map):
        self.map: Map = current_map
        self.facing_dct = {(0, -1): characters.Facing.UP,
                           (0, 1): characters.Facing.DOWN,
                           (-1, 0): characters.Facing.LEFT,
                           (1, 0): characters.Facing.RIGHT}


    def return_path(self, current_node):
        path = []
        current = current_node
        while current is not None:
            path.append(current.position)
            current = current.parent
        return path[::-1]  # Return reversed path

    def astar(self, start, end):
        # Create start and end node
        start_node = Node(None, start)
        start_node.g = start_node.h = start_node.f = 0
        end_node = Node(None, end)
        end_node.g = end_node.h = end_node.f = 0

        # Initialize both open and closed list
        open_list = []
        closed_list = []

        # Heapify the open_list and Add the start node
        heapq.heapify(open_list)
        heapq.heappush(open_list, start_node)

        # Adding a stop condition
        outer_iterations = 0
        # max_iterations = (len(self.map.tuptable_map[0]) * len(self.map.tuptable_map) // 2)
        max_iterations = 30
        # what squares do we search
        adjacent_squares = ((0, -1), (0, 1), (-1, 0), (1, 0),)

        # Loop until you find the end
        while len(open_list) > 0:
            outer_iterations += 1
            if outer_iterations > max_iterations:
                # if we hit this point return the path such as it is
                # it will not contain the destination
                return 0

            # Get the current node
            current_node = heapq.heappop(open_list)
            closed_list.append(current_node)
            

            # Found the goal
            if current_node == end_node:
                return self.return_path(current_node)

            # Generate children
            children = []

            for new_position in adjacent_squares:  # Adjacent squares

                # Get node position
                node_position = (
                    current_node.position[0] + new_position[0], current_node.position[1] + new_position[1])
                # Make sure within range
                if node_position[0] > (len(self.map.tuptable_map) - 1) or node_position[0] < 0 or node_position[1] > (len(self.map.tuptable_map[len(self.map.tuptable_map)-1]) - 1) or node_position[1] < 0:
                    continue

                # Make sure walkable terrain
                if self.map.tuptable_map[node_position[0]][node_position[1]] != 0:
                    continue

                # Create new node
                new_node = Node(current_node, node_position)

                # Append
                children.append(new_node)
            # Loop through children
            for child in children:
                # Child is on the closed list
                if len([closed_child for closed_child in closed_list if closed_child == child]) > 0:
                    continue

                # Create the f, g, and h values
                child.g = current_node.g + 1
                child.h = ((child.position[0] - end_node.position[0]) **
                        2) + ((child.position[1] - end_node.position[1]) ** 2)
                child.f = child.g + child.h

                # Child is already in the open list
                if len([open_node for open_node in open_list if child.position == open_node.position and child.g > open_node.g]) > 0:
                    continue

                # Add the child to the open list
                heapq.heappush(open_list, child)

        return None

    def plan_path(self, raw_path, facing):
        planned_actions = []
        current_position = raw_path.pop(0)

        while raw_path:
            next_position = raw_path[0]
            facing_difference = (next_position[0] - current_position[0], next_position[1] - current_position[1])
            if facing_difference == facing.value:

                planned_actions.append(characters.Action.STEP_FORWARD)
                current_position = raw_path.pop(0)
            
            # XD
            else:
                if (facing_difference[0] == facing.value[0]) or (facing_difference[1] == facing.value[1]):
                    planned_actions.append(characters.Action.TURN_LEFT)
                    facing = facing.turn_left()
                elif facing.value == (0, -1):
                    if facing_difference == (1, 0):
                        planned_actions.append(characters.Action.TURN_RIGHT)
                        facing = facing.turn_right()
                    else:
                        planned_actions.append(characters.Action.TURN_LEFT)
                        facing = facing.turn_left()
                elif facing.value == (1, 0):
                    if facing_difference == (0, 1):
                        planned_actions.append(characters.Action.TURN_RIGHT)
                        facing = facing.turn_right()
                    else:
                        planned_actions.append(characters.Action.TURN_LEFT)
                        facing = facing.turn_left()
                elif facing.value == (0, 1):
                    if facing_difference == (-1, 0):
                        planned_actions.append(characters.Action.TURN_RIGHT)
                        facing = facing.turn_right()
                    else:
                        planned_actions.append(characters.Action.TURN_LEFT)
                        facing = facing.turn_left()
                else:
                    if facing_difference == (0, -1):
                        planned_actions.append(characters.Action.TURN_RIGHT)
                        facing = facing.turn_right()
                    else:
                        planned_actions.append(characters.Action.TURN_LEFT)
                        facing = facing.turn_left()
        return planned_actions

class Node:
    """
    A node class for A* Pathfinding
    """

    def __init__(self, parent=None, position=None):
        self.parent = parent
        self.position = position

        self.g = 0
        self.h = 0
        self.f = 0

    def __eq__(self, other):
        return self.position == other.position

    def __repr__(self):
        return f"{self.position} - g: {self.g} h: {self.h} f: {self.f}"

    # defining less than for purposes of heap queue
    def __lt__(self, other):
        return self.f < other.f

    # defining greater than for purposes of heap queue
    def __gt__(self, other):
        return self.f > other.f
