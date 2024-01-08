from gupb.model import games

from .map import Map



class Environment:
    def __init__(self, map: 'Map'):
        self.episode = 0
        self.episodes_since_mist_increase = 0
        self.map = map

    def environment_action(self, no_of_champions_alive) -> None:
        self.episode += 1
        self.episodes_since_mist_increase += 1

        if self.episodes_since_mist_increase >= games.MIST_TTH_PER_CHAMPION * no_of_champions_alive:
            self.map.increase_mist()
            self.episodes_since_mist_increase = 0
