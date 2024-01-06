import os
from typing import Dict, Optional, List
import bresenham

from gupb.model import arenas, tiles, coordinates, weapons
from gupb.model import characters, consumables, effects
from gupb.model.profiling import profile

from gupb.controller.aragorn import utils
from gupb.controller.aragorn.constants import DEBUG, INFINITY

from .menhir_calculator import MenhirCalculator
from .enemies_positions_approximation import EnemiesPositionsApproximation



class Map:
    def __init__(self, name: str, terrain: arenas.Terrain, memory: 'Memory') -> None:
        self.name = name
        self.terrain: arenas.Terrain = terrain
        self.memory = memory
        
        self.size: tuple[int, int] = arenas.terrain_size(self.terrain)
        self.menhir_position: Optional[coordinates.Coords] = None
        self.mist_radius = int(self.size[0] * 2 ** 0.5) + 1

        self.menhirCalculator = MenhirCalculator(self)
        self.enemiesPositionsApproximation = EnemiesPositionsApproximation(self)

        self.sectionsCenters = None
        self.centerPos = coordinates.Coords(round(self.size[0] / 2), round(self.size[1] / 2))
        self.__dangerousTiles_cache_data = None
        self.__dangerousTiles_cache_tick = 0

        if DEBUG: print("[ARAGORN|MEMORY] loaded map " + self.name + " with size " + str(self.size))

    @staticmethod
    def load(name: str, memory: 'Memory') -> 'Map':
        terrain = dict()

        # predefined map
        # (not used anymore)
        arena_file_path = os.path.join('resources', 'arenas', f'{name}.gupb')
        with open(arena_file_path) as file:
            for y, line in enumerate(file.readlines()):
                for x, character in enumerate(line):
                    if character != '\n':
                        position = coordinates.Coords(x, y)
                        if character in arenas.TILE_ENCODING:
                            terrain[position] = arenas.TILE_ENCODING[character]()
                            terrain[position].seen = arenas.TILE_ENCODING[character] != tiles.Land
                        elif character in arenas.WEAPON_ENCODING:
                            terrain[position] = tiles.Land()
                            terrain[position].loot =  Map.weaponDescriptionConverter(arenas.WEAPON_ENCODING[character]().description())
                            terrain[position].seen = False
        return Map(name, terrain, memory)
    
    @profile
    def visible_coords(self, characterFacing :characters.Facing, characterPosition :coordinates.Coords, characterWeapon :weapons.Weapon = None) -> set[coordinates.Coords]:
        def estimate_border_point() -> tuple[coordinates.Coords, int]:
            if characterFacing == characters.Facing.UP:
                return coordinates.Coords(characterPosition.x, 0), characterPosition[1]
            elif characterFacing == characters.Facing.RIGHT:
                return coordinates.Coords(self.size[0] - 1, characterPosition.y), self.size[0] - characterPosition[0]
            elif characterFacing == characters.Facing.DOWN:
                return coordinates.Coords(characterPosition.x, self.size[1] - 1), self.size[1] - characterPosition.y
            elif characterFacing == characters.Facing.LEFT:
                return coordinates.Coords(0, characterPosition.y), characterPosition[0]

        def champion_left_and_right() -> list[coordinates.Coords]:
            if characterFacing == characters.Facing.UP or characterFacing == characters.Facing.DOWN:
                return [
                    coordinates.Coords(characterPosition.x + 1, characterPosition.y),
                    coordinates.Coords(characterPosition.x - 1, characterPosition.y),
                ]
            elif characterFacing == characters.Facing.LEFT or characterFacing == characters.Facing.RIGHT:
                return [
                    coordinates.Coords(characterPosition.x, characterPosition.y + 1),
                    coordinates.Coords(characterPosition.x, characterPosition.y - 1),
                ]

        border, distance = estimate_border_point()
        left = characterFacing.turn_left().value
        targets = [border + coordinates.Coords(i * left.x, i * left.y) for i in range(-distance, distance + 1)]
        visible = set()
        visible.add(characterPosition)
        for coords in targets:
            ray = bresenham.bresenham(characterPosition.x, characterPosition.y, coords[0], coords[1])
            next(ray)
            for ray_coords in ray:
                if ray_coords not in self.terrain:
                    break
                visible.add(ray_coords)
                if not self.terrain[ray_coords].transparent:
                    break
        if characterWeapon is not None:
            for coords in characterWeapon.prescience(characterPosition, characterFacing):
                if coords in self.terrain:
                    visible.add(coords)
        visible.update(champion_left_and_right())
        return visible
    
    @profile
    def parseVisibleTiles(self, visibleTiles: Dict[coordinates.Coords, tiles.Tile], currentTick :int) -> None:
        self.enemiesPositionsApproximation.update(visibleTiles, currentTick)
        
        for coords in visibleTiles:
            visible_tile_description = visibleTiles[coords]
            
            if not coords in self.terrain:
                self.terrain[coords] = tiles.Land()
            
            if self.terrain[coords].__class__.__name__.lower() != visible_tile_description.type:
                newType = None

                if visible_tile_description.type == 'land':
                    newType = tiles.Land
                elif visible_tile_description.type == 'sea':
                    newType = tiles.Sea
                elif visible_tile_description.type == 'wall':
                    newType = tiles.Wall
                elif visible_tile_description.type == 'menhir':
                    newType = tiles.Menhir

                    if isinstance(coords, coordinates.Coords):
                        coordsWithCorrectType = coords
                    elif isinstance(coords, tuple):
                        coordsWithCorrectType = coordinates.Coords(coords[0], coords[1])
                    else:
                        coordsWithCorrectType = coords
                        if DEBUG:
                            print("[Map] Trying to set menhir pos to non Coords object (" + str(coords) + " of type " + str(type(coords)) + ")")
                    
                    self.menhir_position = coordsWithCorrectType
                    self.menhirCalculator.setMenhirPos(coordsWithCorrectType)
                else:
                    newType = tiles.Land
                
                self.terrain[coords] = newType()
            
            self.terrain[coords].tick = currentTick
            self.terrain[coords].seen = True
            self.terrain[coords].loot = Map.weaponDescriptionConverter(visible_tile_description.loot)
            self.terrain[coords].character = visible_tile_description.character
            
            if coords == self.memory.position:
                self.terrain[coords].character = None
            
            self.terrain[coords].consumable = self.consumableDescriptionConverter(visible_tile_description.consumable)
            
            tileEffects = self.effectsDescriptionConverter(visible_tile_description.effects)
            self.terrain[coords].effects = tileEffects

            if effects.Mist in tileEffects:
                self.menhirCalculator.addMist(coords, tick=currentTick)
    
    @staticmethod
    def weaponDescriptionConverter(weaponDescription: weapons.WeaponDescription) -> weapons.Weapon:
        if weaponDescription is None or not isinstance(weaponDescription, weapons.WeaponDescription):
            return None
        
        if weaponDescription.name == 'knife':
            return weapons.Knife
        elif weaponDescription.name == 'sword':
            return weapons.Sword
        elif weaponDescription.name == 'axe':
            return weapons.Axe
        elif weaponDescription.name in ['bow', 'bow_loaded', 'bow_unloaded']:
            return weapons.Bow
        elif weaponDescription.name == 'amulet':
            return weapons.Amulet
        else:
            return None
    
    def consumableDescriptionConverter(self, consumableDescription: consumables.ConsumableDescription) -> consumables.Consumable:
        if consumableDescription is None or not isinstance(consumableDescription, consumables.ConsumableDescription):
            return None
        
        if consumableDescription.name == 'potion':
            return consumables.Potion
        return None
    
    def effectsDescriptionConverter(self, effectsToConvert: List[effects.EffectDescription]) -> list[effects.Effect]:
        convertedEffects = []

        for effect in effectsToConvert:
            if effect.type == 'mist':
                convertedEffects.append(effects.Mist)
            elif effect.type == 'weaponcut':
                convertedEffects.append(effects.WeaponCut)
        
        return convertedEffects
    
    def increase_mist(self) -> None:
        self.mist_radius -= 1 if self.mist_radius > 0 else self.mist_radius
    
    def getClosestWeaponPos(self, searchedWeaponType: weapons.Weapon|None, currentPos: coordinates.Coords = None):
        closestCoords = None
        closestDistance = INFINITY

        for coords in self.terrain:
            weapon = self.terrain[coords].loot

            if (
                # take this tile's wapon into consideretion if
                # did not requested any specific searchedWeaponType
                searchedWeaponType is None
                # or the weapon is the one we are looking for
                or (
                    weapon is not None
                    and weapon == searchedWeaponType
                )
            ):
                if currentPos is None:
                    return coords
                
                distance = utils.manhattanDistance(currentPos, coords)

                if distance < closestDistance:
                    closestCoords = coords
                    closestDistance = distance
        
        return closestCoords
    
    @profile
    def getDangerousTilesWithDangerSourcePos(self, currentTick :int = None, maxTicksBehind :int = None):
        """
        Returns a dict. Keys are coords with danger, values are their sources
        """

        NOT_DANGEROUS_OPPONENTS = [
            'Cynamonka',
            'RandomControllerAlice',
        ]

        # cache
        if currentTick is not None and self.__dangerousTiles_cache_data is not None and self.__dangerousTiles_cache_tick == currentTick:
            return self.__dangerousTiles_cache_data



        dangerousTiles = {}

        for coords in self.terrain:
            if currentTick is not None and maxTicksBehind is not None and hasattr(self.terrain[coords], 'tick'):
                if self.terrain[coords].tick < currentTick - maxTicksBehind:
                    continue
            
            enemyDescription = self.terrain[coords].character


            if (
                enemyDescription is not None
                and coords != self.memory.position
                and enemyDescription.controller_name not in NOT_DANGEROUS_OPPONENTS
            ):
                weapon = Map.weaponDescriptionConverter(enemyDescription.weapon)

                if weapon is None:
                    continue

                positions = weapon.cut_positions(self.terrain, coords, enemyDescription.facing)

                for position in positions:
                    if position not in dangerousTiles:
                        dangerousTiles[position] = coords
            
            # Make mist dangerous
            # if effects.Mist in self.terrain[coords].effects:
            #     dangerousTiles[coords] = coords

            # Watch out for damage
            if (
                effects.WeaponCut in self.terrain[coords].effects
                and hasattr(self.terrain[coords], 'tick')
                and self.terrain[coords].tick >= currentTick - 2
            ):
                dangerousTiles[coords] = coords

        
        # cache
        if currentTick is not None:
            self.__dangerousTiles_cache_data = dangerousTiles
            self.__dangerousTiles_cache_tick = currentTick
        
        return dangerousTiles
    
    def getSectionsCenters(self):
        """
        Divides map to 5 sections and returns their centers

        ul -> up left
        ur -> up right
        dl -> down left
        dr -> dorn right

        .-----------------.
        |        |        |
        |  1   __|__   2  |
        |     |     |     |
        |-----|  0  |-----|
        |     |__ __|     |
        |  3     |     4  |      
        |        |        |
        `-----------------`
        """

        # cache
        if self.sectionsCenters is not None:
            return self.sectionsCenters
        
        # get map's center
        center = coordinates.Coords(self.size[0] / 2, self.size[1] / 2)
        center = coordinates.Coords(round(center.x), round(center.y))

        # define map corners
        ul_corner = coordinates.Coords(0, 0)
        ur_corner = coordinates.Coords(self.size[0], 0)
        dl_corner = coordinates.Coords(0, self.size[1])
        dr_corner = coordinates.Coords(self.size[0], self.size[1])

        # calculate distance from center to corners
        ul_distance = coordinates.sub_coords(ul_corner, center)
        ur_distance = coordinates.sub_coords(ur_corner, center)
        dl_distance = coordinates.sub_coords(dl_corner, center)
        dr_distance = coordinates.sub_coords(dr_corner, center)

        # get 2/3 of distance
        ul_distance = coordinates.mul_coords(ul_distance, 2/3)
        ur_distance = coordinates.mul_coords(ur_distance, 2/3)
        dl_distance = coordinates.mul_coords(dl_distance, 2/3)
        dr_distance = coordinates.mul_coords(dr_distance, 2/3)
        
        # round distance to ensure that section's center coords are integers
        ul_distance = coordinates.Coords(round(ul_distance.x), round(ul_distance.y))
        ur_distance = coordinates.Coords(round(ur_distance.x), round(ur_distance.y))
        dl_distance = coordinates.Coords(round(dl_distance.x), round(dl_distance.y))
        dr_distance = coordinates.Coords(round(dr_distance.x), round(dr_distance.y))

        # add distance to center to get section's center coords
        ul_center = coordinates.add_coords(center, ul_distance)
        ur_center = coordinates.add_coords(center, ur_distance)
        dl_center = coordinates.add_coords(center, dl_distance)
        dr_center = coordinates.add_coords(center, dr_distance)

        # find closest land tile to section's center
        ul_center = utils.closestTileFromWithCondition(ul_center, lambda coords: self.terrain[coords].__class__.__name__.lower() == 'land', 30, ul_center)
        ur_center = utils.closestTileFromWithCondition(ur_center, lambda coords: self.terrain[coords].__class__.__name__.lower() == 'land', 30, ur_center)
        dl_center = utils.closestTileFromWithCondition(dl_center, lambda coords: self.terrain[coords].__class__.__name__.lower() == 'land', 30, dl_center)
        dr_center = utils.closestTileFromWithCondition(dr_center, lambda coords: self.terrain[coords].__class__.__name__.lower() == 'land', 30, dr_center)
        
        # return section's centers
        self.sectionsCenters = [
            center,
            ul_center,
            ur_center,
            dl_center,
            dr_center
        ]

        return self.sectionsCenters
