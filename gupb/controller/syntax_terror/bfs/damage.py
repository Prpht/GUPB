from gupb.model import coordinates, tiles
from ..mist import MistInfo, is_pos_mist_at
from ..weapons import attack_damage
from .constants import LOS_TRANSPARENT_TYPES

# Flat traversal cost added for stepping into a cell within an enemy's attack
# range. This makes the bot route *around* enemies without being punished
# exponentially (as it would be if the damage was treated as real HP loss).
ENEMY_RANGE_PENALTY: int = 5


def _step_hp_loss(
    nxt_pos: coordinates.Coords,
    nxt_tile: tiles.TileDescription,
    ticks_ahead: int,
    mist_info: MistInfo | None,
    attacked_cells: dict[coordinates.Coords, int],
    self_hp: int,
    self_pos: coordinates.Coords,
) -> int:
    hp_loss = 0
    effect_types = {e.type for e in nxt_tile.effects}
    if "fire" in effect_types:
        hp_loss += 3
    elif "mist" in effect_types:
        hp_loss += 1

    if mist_info and is_pos_mist_at(mist_info, nxt_pos, ticks_ahead):
        hp_loss += 1

    # Enemy-inflicted damage is intentionally NOT counted as HP loss. We instead
    # add a small flat cost for entering enemy range (see _enemy_range_penalty),
    # so the bot avoids enemies rather than treating contact as lethal damage.
    # To restore HP-based (exponential) enemy avoidance, flip `if False:` below.
    if False:  # noqa: SIM223 - enemy attack damage as real HP loss (disabled)
        if nxt_pos in attacked_cells:
            hp_loss += attacked_cells[nxt_pos]
        if nxt_tile.character and nxt_pos != self_pos:
            hp_loss += attack_damage(nxt_tile.character.weapon.name)

    return hp_loss


def _enemy_range_penalty(
    nxt_pos: coordinates.Coords,
    attacked_cells: dict[coordinates.Coords, int],
    ticks_ahead: int,
) -> int:
    if nxt_pos in attacked_cells:
        return round(ENEMY_RANGE_PENALTY * (0.85 ** (ticks_ahead - 1)))
    return 0


def _enemy_attack_cells(
    start: coordinates.Coords,
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    ignored_enemy_pos: coordinates.Coords | None = None,
) -> dict[coordinates.Coords, int]:
    from ..combat.arena import _attack_cells

    class DummyArena:
        def __init__(self, known_map):
            self.origin = (0, 0)
            self.size = 100
            self.terrain_transparent = frozenset(
                pos
                for pos, tile in known_map.items()
                if tile.character is None and tile.type in LOS_TRANSPARENT_TYPES
            )
            self.known = frozenset(known_map.keys())

    arena = DummyArena(known_map)
    attacked = {}
    for pos, tile in known_map.items():
        if tile.character is not None and pos != start and pos != ignored_enemy_pos:
            w_name = tile.character.weapon.name
            cells = _attack_cells(w_name, pos, tile.character.facing, arena)
            dmg = attack_damage(w_name)
            for cell in cells:
                attacked[cell] = max(attacked.get(cell, 0), dmg)
    return attacked
