import sys
sys.path.append('.')

import unittest

from gupb.controller.ares.ares_controller import Map
from gupb.model.characters import ChampionKnowledge, Action
from gupb.model import arenas
from gupb.model import effects
from gupb.model.coordinates import Coords
from gupb.model import consumables
from gupb.model.tiles import TileDescription, Tile
from gupb.model.weapons import WeaponDescription
from gupb.model.characters import ChampionDescription, Facing


class MapTestSuite(unittest.TestCase):
    def testUpdate(self, map):
        visTiles = {
            Coords(6, 3): TileDescription(type='land', loot=WeaponDescription(name='axe'), character=None, consumable=None, effects=[]), 
            Coords(7, 8): TileDescription(type='wall', loot=None, character=None, consumable=None, effects=[effects.Mist()])
        }
        knowledge = ChampionKnowledge(
            Coords(0, 0),
            1,
            visTiles
        )
        map.update(knowledge)

        self.assertEqual(map.opponentsAlive, 0)
        self.assertEqual(map.position, Coords(0, 0))
        self.assertEqual(map.MAPSIZE, (10, 10))
        self.assertIsNotNone(map.map)
        
        self.assertEqual(map.map[6][3].loot.name, 'axe')
        self.assertEqual(len(map.map[7][8].effects), 1)
        self.assertEqual(map.map[7][8].effects[0].description().type, 'mist')
        print("testUpdate PASSED")

    def testLoadMini(self, map):
        self.assertEqual(map.map[0][0].description().type, 'sea')
        self.assertEqual(map.map[1][1].description().type, 'land')
        self.assertEqual(map.map[1][2].description().type, 'wall')
        self.assertEqual(map.map[9][9].description().type, 'sea')
        self.assertEqual(map.map[5][2].description().loot.name, 'sword')
        print("testLoadMini PASSED")
    
    def testShortestPathSword(self, map):
        map.position = Coords(1, 1)
        map.description = ChampionDescription(
            'Nike',
            8,
            None,
            Facing.UP
        )

        pathToSword, swordCoords = map.findTarget(WeaponDescription(name='sword'))
        path = [
            Action.TURN_RIGHT,
            Action.TURN_RIGHT,
            Action.STEP_FORWARD,
            Action.STEP_FORWARD,
            Action.STEP_FORWARD,
            Action.STEP_FORWARD,
            Action.TURN_LEFT,
            Action.STEP_FORWARD
        ]
        for i, step in enumerate(pathToSword):
            self.assertEqual(step, path[i])
        self.assertEqual(swordCoords, Coords(5, 2))
        print("testShortestPath PASSED")

    def full_test(self):
        arena_desc = 'mini'
        map = Map(arena_description=arena_desc)
        self.testLoadMini(map)
        self.testUpdate(map)
        self.testShortestPathSword(map)


if __name__ == "__main__":
    MTS = MapTestSuite()
    MTS.full_test()