from gupb.controller.lord_icon.distance import dist, find_path
from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.controller.lord_icon.move import MoveController
from gupb.controller.lord_icon.strategies.core import Strategy
from gupb.model.characters import Action


def nearest_safe_spot(map, pos, n, m):
    nearest_point = (3000, 3000)
    for i in range(1, n):
        for j in range(1, m):
            if map[i][j] == 0 and dist(pos, (i, j)) < dist(pos, nearest_point):
                nearest_point = (i, j)
    return nearest_point


class CampStrategy(Strategy):
    name = "CampStrategy"
    nearest_spot = (0, 0)
    counter = 0

    @staticmethod
    def get_action(knowledge: Knowledge):
        cam_spot_map = {}
        if CampStrategy.nearest_spot == (0, 0):
            n, m = knowledge.arena.size
            camp_spots = [(0, 0), (0, knowledge.arena.size[1]), (knowledge.arena.size[0], 0), knowledge.arena.size]
            for pos in camp_spots:
                safe_spot = nearest_safe_spot(knowledge.map, pos, n, m)
                cam_spot_map[safe_spot] = dist(knowledge.position, safe_spot)
            sorted_spots = dict(sorted(cam_spot_map.items(), key=lambda item: item[1]))
            if len(sorted_spots) > 0:
                CampStrategy.nearest_spot = next(iter(sorted_spots))
        else:
            moves = find_path(knowledge.map, knowledge.character.position, CampStrategy.nearest_spot)
            if len(moves) > 0:
                return MoveController.next_move(knowledge, moves[0])

        return Action.TURN_LEFT
