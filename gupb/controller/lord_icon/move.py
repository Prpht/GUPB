

from gupb.controller.lord_icon.distance import Point2d
from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.model.characters import Action, Facing


class MoveController:

    @staticmethod
    def next_move(knowledge: Knowledge, goal: Point2d) -> Action:
        position = knowledge.character.position
        current_facing = knowledge.character.facing

        diff = goal[0] - position[0], goal[1] - position[1]
        goal_facing = Facing(diff)

        if current_facing == goal_facing:
            return Action.STEP_FORWARD

        if current_facing == Facing.UP:
            if goal_facing == Facing.RIGHT:
                return Action.TURN_RIGHT

            if goal_facing == Facing.LEFT:
                return Action.TURN_LEFT

        if current_facing == Facing.DOWN:
            if goal_facing == Facing.RIGHT:
                return Action.TURN_LEFT

            if goal_facing == Facing.LEFT:
                return Action.TURN_RIGHT

        if current_facing == Facing.RIGHT:
            if goal_facing == Facing.UP:
                return Action.TURN_LEFT

            if goal_facing == Facing.DOWN:
                return Action.TURN_RIGHT

        if current_facing == Facing.LEFT:
            if goal_facing == Facing.UP:
                return Action.TURN_RIGHT

            if goal_facing == Facing.DOWN:
                return Action.TURN_LEFT

        return Action.TURN_LEFT
