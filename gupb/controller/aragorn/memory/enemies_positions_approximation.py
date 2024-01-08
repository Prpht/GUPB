from typing import Dict, List

from gupb.model import characters, coordinates, tiles

from gupb.controller.aragorn.constants import DEBUG, OUR_BOT_NAME



class EnemiesPositionsApproximation:
    LOW_PROBABILITY_AFTER_MOVES = 8

    def __init__(self, map: 'Map') -> None:
        self.enemies = {}
        self.map = map
        self.enemiesTiles = {}
        self.lastSeenAt = {}
    
    def _removeEnemy(self, enemyName: str) -> None:
        if enemyName not in self.enemies:
            return
        
        # enemiesTiles
        for coordsToDel in self.enemies[enemyName]:
            coordsAreInOtherEnemy = False

            for tmpEnemyName, tmpEnemyTiles in self.enemies.items():
                if tmpEnemyName != enemyName:
                    if coordsToDel in tmpEnemyTiles:
                        coordsAreInOtherEnemy = True
                        break
            
            if not coordsAreInOtherEnemy and coordsToDel in self.enemiesTiles:
                del self.enemiesTiles[coordsToDel]
        # ===
        del self.enemies[enemyName]

    def update(self, visibleTiles: Dict[coordinates.Coords, tiles.Tile], crurentTick :int):
        self.parseVisibleTiles(visibleTiles, crurentTick)
    
    def whereCanOneGoFrom(self, coords: coordinates.Coords) -> List[coordinates.Coords]:
        neighbours = []

        for direction in characters.Facing:
            neighbour = coordinates.add_coords(coords, direction.value)

            if neighbour in self.map.terrain and self.map.terrain[neighbour].terrain_passable():
                neighbours.append(neighbour)
        
        return neighbours

    def parseVisibleTiles(self, visibleTiles: Dict[coordinates.Coords, tiles.Tile], tick: int) -> None:
        # remove enemies with low probability
        enemiesToRemove = []

        for enemyName, lastSeenAtTick in self.lastSeenAt.items():
            if tick - lastSeenAtTick > self.LOW_PROBABILITY_AFTER_MOVES:
                enemiesToRemove.append(enemyName)
        
        for enemyName in enemiesToRemove:
            self._removeEnemy(enemyName)

        # simulate unseen movements
        for enemyName, enemyPossiblePositions in self.enemies.items():
            newTiles = []

            for enCoords in enemyPossiblePositions:
                neighboringCoords = self.whereCanOneGoFrom(enCoords)

                for nCoord in neighboringCoords:
                    if nCoord not in enemyPossiblePositions and nCoord not in newTiles:
                        newTiles.append(nCoord)
            
            self.enemies[enemyName] += newTiles
            
            # enemiesTiles
            for nt in newTiles:
                self.enemiesTiles[nt] = True
            # ===

        # confront simulated knowledge with visible tiles
        for coords in visibleTiles:
            visible_tile_description = visibleTiles[coords]
            
            if visible_tile_description.character is not None and visible_tile_description.character.controller_name != OUR_BOT_NAME:
                # enemy found
                enemyName = visible_tile_description.character.controller_name

                if isinstance(coords, tuple):
                    coords = coordinates.Coords(coords[0], coords[1])
                
                self.lastSeenAt[enemyName] = tick
                self._removeEnemy(enemyName)
                self.enemies[enemyName] = [coords]
                # enemiesTiles
                self.enemiesTiles[coords] = True
                # ===
            else:
                # no enemy found
                for enemyName, enemyPossiblePositions in self.enemies.items():
                    if coords in enemyPossiblePositions:
                        enemyPossiblePositions.remove(coords)
                        
                        # enemiesTiles
                        if coords in self.enemiesTiles:
                            del self.enemiesTiles[coords]
                        # ===
    
    def getEnemiesTilesPlusRadius(self, radius):
        enemiesTiles = list(self.enemiesTiles.keys())

        for _ in range(radius):
            newTiles = []

            for coords in enemiesTiles:
                neighboringCoords = self.whereCanOneGoFrom(coords)

                for nCoord in neighboringCoords:
                    if nCoord not in enemiesTiles and nCoord not in newTiles:
                        newTiles.append(nCoord)
                
            enemiesTiles += newTiles
        
        return enemiesTiles
    
    def getEnemiesTiles(self):
        return list(self.enemiesTiles.keys())
