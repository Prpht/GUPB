from gupb.model import arenas, coordinates, weapons
from gupb.model import characters



class Memory:
    def __init__(self):
        self.position: coordinates.Coords = None
        no_of_champions_alive: int = 0

    def update(self, knowledge: characters.ChampionKnowledge) -> None:
        self.position = knowledge.position
        self.no_of_champions_alive = knowledge.no_of_champions_alive
