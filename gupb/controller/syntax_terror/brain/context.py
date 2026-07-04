from dataclasses import dataclass

from gupb.model import characters, coordinates, tiles

from ..bfs.cache import DistanceMap
from ..bfs.turn_nav import TurnNavigation
from ..memory import MapMemory


def _self_tile(
    knowledge: characters.ChampionKnowledge,
    memory: MapMemory,
) -> tiles.TileDescription | None:
    tile = knowledge.visible_tiles.get(knowledge.position)
    if tile is not None:
        return tile
    return memory.map_data.get(knowledge.position)


def self_facing(
    knowledge: characters.ChampionKnowledge,
    memory: MapMemory,
) -> characters.Facing:
    tile = _self_tile(knowledge, memory)
    if tile and tile.character:
        return tile.character.facing
    return characters.Facing.UP


def self_stats(
    knowledge: characters.ChampionKnowledge,
    memory: MapMemory,
) -> tuple[int, str]:
    tile = _self_tile(knowledge, memory)
    if tile and tile.character:
        weapon_name = tile.character.weapon.name
        if weapon_name == "scroll":
            weapon_name = f"scroll_{memory.my_scroll_charges}"
        return tile.character.health, weapon_name
    return characters.CHAMPION_STARTING_HP, "knife"


def is_omnidirectional(weapon_name: str) -> bool:
    return weapon_name == "amulet"


def _on_mist(memory: MapMemory, position: coordinates.Coords) -> bool:
    tile = memory.map_data.get(position)
    return bool(tile and any(e.type == "mist" for e in tile.effects))


def _on_fire(memory: MapMemory, position: coordinates.Coords) -> bool:
    tile = memory.map_data.get(position)
    return bool(tile and any(e.type == "fire" for e in tile.effects))


@dataclass(frozen=True, slots=True)
class TurnContext:
    knowledge: characters.ChampionKnowledge
    memory: MapMemory
    facing: characters.Facing
    hp: int
    weapon: str
    omni: bool
    bfs_omni: bool
    distances: DistanceMap


def build_turn_context(
    knowledge: characters.ChampionKnowledge,
    memory: MapMemory,
    facing: characters.Facing,
    hp: int,
    weapon: str,
) -> TurnContext:
    omni = is_omnidirectional(weapon)
    
    from ..bfs.damage import _enemy_attack_cells
    under_attack = knowledge.position in _enemy_attack_cells(knowledge.position, memory.map_data)
    
    bfs_omni = (
        omni
        or _on_mist(memory, knowledge.position)
        or _on_fire(memory, knowledge.position)
        or under_attack
    )
    turn_nav = TurnNavigation.build(memory, knowledge.position, hp, memory.map_data)
    return TurnContext(
        knowledge=knowledge,
        memory=memory,
        facing=facing,
        hp=hp,
        weapon=weapon,
        omni=omni,
        bfs_omni=bfs_omni,
        distances=turn_nav.forward,
    )
