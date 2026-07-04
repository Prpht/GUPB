import numpy as np

from gupb.model import characters

EFFECTS = ["none", "mist", "weaponcut", "fire"]
WEAPONS = [
    "none",
    "knife",
    "sword",
    "axe",
    "bow_unloaded",
    "bow_loaded",
    "amulet",
    "scroll",
]
HEALTH_AVERAGE = 10


class GUPBWrapper:
    def __init__(self, view_radius=7):
        self.view_radius = view_radius
        self.channels = 8
        self.height = 16
        self.width = 16
        self.menhir_position = None

    def facing_val(self, tile):
        if tile.character:
            facing = tile.character.facing
            if facing.value == (0, -1):
                facing_val = 1  # UP
            elif facing.value == (1, 0):
                facing_val = 2  # RIGHT
            elif facing.value == (0, 1):
                facing_val = 3  # DOWN
            elif facing.value == (-1, 0):
                facing_val = 4  # LEFT
            else:
                return 0.0

            return facing_val / 4.0

        else:
            return 0.0

    def health_encode(self, health: int) -> float:
        return round(health / (health + HEALTH_AVERAGE), 2)

    def encode(self, knowledge: characters.ChampionKnowledge):
        # 1. Obstacles, 2. Own position, 3. Visible enemies, 4. Weapons, 5. Consumables, 6. Facing direction., 7. Effects, 8. Char Weapons
        obs = np.zeros((self.channels, self.height, self.width), dtype=np.float32)

        center_x, center_y = knowledge.position[0], knowledge.position[1]

        for coords, tile_desc in knowledge.visible_tiles.items():
            dx = coords[0] - center_x
            dy = coords[1] - center_y

            # Map to array indices
            nx = dx + 8
            ny = dy + 8

            # Cache menhir pos if seen
            if not self.menhir_position and tile_desc.type == "menhir":
                self.menhir_position = coords

            if 0 <= nx < self.width and 0 <= ny < self.height:
                if tile_desc.type in ["wall", "sea"]:
                    obs[0, ny, nx] = 1.0

                if dx == 0 and dy == 0:
                    if tile_desc.character:
                        obs[1, ny, nx] = self.health_encode(tile_desc.character.health)
                        obs[5, ny, nx] = self.facing_val(tile_desc)
                        obs[7, ny, nx] = (
                            WEAPONS.index(tile_desc.character.weapon.name) / 10.0
                        )
                else:
                    if tile_desc.character:
                        obs[2, ny, nx] = self.health_encode(tile_desc.character.health)
                        obs[5, ny, nx] = self.facing_val(tile_desc)
                        obs[7, ny, nx] = (
                            WEAPONS.index(tile_desc.character.weapon.name) / 10.0
                        )

                if tile_desc.loot:
                    obs[3, ny, nx] = WEAPONS.index(tile_desc.loot.name) / 10.0

                if tile_desc.consumable:
                    obs[4, ny, nx] = 1.0

                if tile_desc.effects:
                    obs[6, ny, nx] = EFFECTS.index(tile_desc.effects[0].type) / 4.0

        if self.menhir_position:
            mx, my = self.menhir_position

            cx = (mx - center_x) + 8
            cy = (my - center_y) + 8

            if 0 <= cx < self.width and 0 <= cy < self.height:
                obs[0, cy, cx] = 0.5

        return obs
