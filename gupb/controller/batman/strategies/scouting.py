from gupb.model.coordinates import Coords
from gupb.model.characters import Action
from gupb.model.weapons import Knife, Sword, Axe, Bow, Amulet
from gupb.controller.batman.navigation import Navigation
from gupb.controller.batman.environment.knowledge import (
    Knowledge,
    ArenaKnowledge,
    TileKnowledge,
    ChampionKnowledge,
    WeaponKnowledge,
    ConsumableKnowledge
)
from gupb.controller.batman.events import (
    Event,
    MenhirFoundEvent,
    WeaponFoundEvent,
    WeaponPickedUpEvent,
    ConsumableFoundEvent,
    LosingHealthEvent,
    EnemyFoundEvent
)

WEAPON_TO_CLASS = {
    "knife": Knife,
    "sword": Sword,
    "axe": Axe,
    "bow": Bow,
    "bow_loaded": Bow,
    "bow_unloaded": Bow,
    "amulet": Amulet
}


# TODO move this elsewhere
def weapon_cut_positions(knowledge: Knowledge) -> list[Coords]:
    weapon_class = WEAPON_TO_CLASS[knowledge.champion.weapon]
    cut_positions = weapon_class.cut_positions(
        knowledge.arena.arena.terrain,
        knowledge.champion.position,
        knowledge.champion.facing
    )
    return cut_positions


class ScoutingStrategy:
    def __init__(self):
        self._current_objective = None
        self._current_objective_name = None

    def decide(self, knowledge: Knowledge, events: list[Event], navigation: Navigation) -> tuple[Action, str]:
        if knowledge.position == self._current_objective:
            if self._current_objective_name == "menhir" and knowledge.champion.weapon != "knife":
                return Action.ATTACK, "defending"

            self._current_objective = None
            self._current_objective_name = None

        for event in events:
            if isinstance(event, MenhirFoundEvent):
                self._current_objective = event.position
                self._current_objective_name = "menhir"
            if isinstance(event, WeaponFoundEvent):
                if (knowledge.champion.weapon == "knife" and self._current_objective_name != "axe") \
                        or (event.weapon.name == "axe" and knowledge.champion.weapon != "axe"):
                    self._current_objective = event.weapon.position
                    self._current_objective_name = event.weapon.name
            if isinstance(event, WeaponPickedUpEvent):
                if knowledge.arena.menhir_position:
                    self._current_objective = knowledge.arena.menhir_position
                    self._current_objective_name = "menhir"
            if isinstance(event, ConsumableFoundEvent):
                if knowledge.champion.health <= 5:
                    self._current_objective = event.consumable.position
                    self._current_objective_name = event.consumable.name
            if isinstance(event, EnemyFoundEvent):
                if event.champion.position in weapon_cut_positions(knowledge):
                    return Action.ATTACK, "scouting"
            # if isinstance(event, LosingHealthEvent):  # TODO this should give us a hint about the enemy position
            #     if knowledge.champion.health <= 5:
            #         # TODO better to turn to the side, which is not occupied by the wall or sea
            #         return Action.ATTACK, "defending"

        # if we are not doing anything, we should go to the menhir
        if self._current_objective is None and knowledge.arena.menhir_position:
            self._current_objective = knowledge.arena.menhir_position
            self._current_objective_name = "menhir"

        # if no objective is set, we should scout the map
        # currently we are looking for the furthest tile from the champion, and we are going there
        if self._current_objective is None:
            champion_position = knowledge.champion.position
            max_distance = 0
            for position, tile in knowledge.arena.explored_map.items():
                if not tile.passable:
                    continue

                distance = navigation.manhattan_distance(champion_position, position)
                if distance > max_distance:
                    max_distance = distance
                    self._current_objective = position
                    self._current_objective_name = "scouting"

            # if we look straight at the wall, we should turn right
            if max_distance == 0:
                return Action.TURN_RIGHT, "scouting"

        # print(self._current_objective_name, knowledge.position, self._current_objective)
        return navigation.next_step(knowledge, self._current_objective), "scouting"
