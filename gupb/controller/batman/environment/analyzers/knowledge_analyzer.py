from gupb.model.coordinates import Coords
from gupb.controller.batman.environment.knowledge import Knowledge, ArenaKnowledge, TileKnowledge
from gupb.controller.batman.environment.analyzers.tile_analyzer import TileAnalyzer


class KnowledgeAnalyzer:
    def __init__(self, knowledge: Knowledge):
        self.knowledge = knowledge
        self.arena = knowledge.arena

    def tile_analyzer(self, position: Coords) -> TileAnalyzer:
        return TileAnalyzer(self.knowledge, position)
