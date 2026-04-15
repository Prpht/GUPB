from typing import Optional

from gupb.model import characters
from gupb.model.coordinates import Coords


class Navigator:
    
    @staticmethod
    def _get_my_facing(knowledge: characters.ChampionKnowledge):
        my_tile = knowledge.visible_tiles[knowledge.position]
        return my_tile.character.facing
    
    @staticmethod
    def _facing_to_vector(facing) -> Coords:
        if facing == characters.Facing.UP:
            return Coords(0, -1)
        if facing == characters.Facing.DOWN:
            return Coords(0, 1)
        if facing == characters.Facing.LEFT:
            return Coords(-1, 0)
        return Coords(1, 0)
    
    @staticmethod
    def _get_front_coords(position: Coords, facing) -> Coords:
        return position + Navigator._facing_to_vector(facing)
    
    @staticmethod
    def _get_tile(knowledge: characters.ChampionKnowledge, coords: Coords):
        return knowledge.visible_tiles.get(coords)
    
    @staticmethod
    def _is_blocked(tile) -> bool:
        if tile is None:
            return True
        return tile.type in {"wall", "sea"}
    
    @staticmethod
    def _enemy_ahead(knowledge: characters.ChampionKnowledge) -> bool:
        position = knowledge.position
        facing = Navigator._get_my_facing(knowledge)
        front_coords = Navigator._get_front_coords(position, facing)
        front_tile = Navigator._get_tile(knowledge, front_coords)

        if front_tile is None:
            return False
        return front_tile.character is not None
    
    @staticmethod
    def _enemy_visible(knowledge: characters.ChampionKnowledge) -> bool:
        my_position = knowledge.position
        for coords, tile in knowledge.visible_tiles.items():
            if coords == my_position:
                continue
            if tile.character is not None:
                return True
        return False
    
    @staticmethod
    def _loot_visible(knowledge: characters.ChampionKnowledge) -> bool:
        for _, tile in knowledge.visible_tiles.items():
            if tile.loot is not None:
                return True
        return False
    
    @staticmethod
    def _consumable_visible(knowledge: characters.ChampionKnowledge) -> bool:
        for _, tile in knowledge.visible_tiles.items():
            if tile.consumable is not None:
                return True
        return False
    
    @staticmethod
    def _is_mist_visible(knowledge: characters.ChampionKnowledge) -> bool:
        return any(
            any(effect.type == "mist" for effect in tile.effects)
            for tile in knowledge.visible_tiles.values()
    )

    @staticmethod
    def _find_menhir(knowledge: characters.ChampionKnowledge) -> Optional[Coords]:
        for coords, tile in knowledge.visible_tiles.items():
            if tile.type == "menhir":
                return coords
        return None

    @staticmethod
    def update_blocking_tiles(
        knowledge: characters.ChampionKnowledge,
        blocking_tiles: set[Coords],
    ) -> None:
        for coords, tile in knowledge.visible_tiles.items():
            if tile.type == "wall" or tile.type == "sea":
                blocking_tiles.add(Coords(coords[0], coords[1]))
        return blocking_tiles

    @staticmethod
    def _closest_enemy(knowledge: characters.ChampionKnowledge) -> Optional[Coords]:
        my_pos = knowledge.position
        best = None
        best_dist = float("inf")

        for coords, tile in knowledge.visible_tiles.items():
            if tile.character is None or Coords(coords[0], coords[1])==my_pos:
                continue
            
            d = abs(coords[0]- my_pos[1]) + abs(coords[1] - my_pos[1])
            if d < best_dist:
                best_dist = d
                best = coords
                
        return best
    
    @staticmethod
    def _is_blocking_in_line(start: Coords, end: Coords, blocking_tiles: set) -> bool:
        if start.x != end.x:
            step = 1 if end.x > start.x else -1
            for x in range(start.x + step, end.x, step):
                if Coords(x, start.y) in blocking_tiles:
                    return True

        if start.y != end.y:
            step = 1 if end.y > start.y else -1
            for y in range(start.y + step, end.y, step):
                if Coords(start.x, y) in blocking_tiles:
                    return True

        return False
    