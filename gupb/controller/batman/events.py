from typing import Optional
from enum import IntEnum, auto
from copy import deepcopy

from gupb.controller.batman.environment.knowledge import (
    Knowledge,
    ArenaKnowledge,
    TileKnowledge,
    ChampionKnowledge,
    WeaponKnowledge,
    ConsumableKnowledge
)


class Event:
    @property
    def name(self):
        raise NotImplementedError()


class MenhirFoundEvent(Event):
    name = "menhir_found"

    def __init__(self, position):
        self.position = position


class WeaponFoundEvent(Event):
    name = "weapon_found"

    def __init__(self, weapon: WeaponKnowledge):
        self.weapon = weapon


class WeaponPickedUpEvent(Event):
    name = "weapon_picked_up"

    def __init__(self, weapon_name: str):
        self.weapon_name = weapon_name


class ConsumableFoundEvent(Event):
    name = "consumable_found"

    def __init__(self, consumable: ConsumableKnowledge):
        self.consumable = consumable


class LosingHealthEvent(Event):
    name = "losing_health"

    def __init__(self, damage: int):
        self.damage = damage


class EnemyFoundEvent(Event):
    name = "enemy_found"

    def __init__(self, champion: ChampionKnowledge):
        self.champion = champion


class EventDetector:
    def __init__(self):
        self._previous_knowledge: Optional[Knowledge] = None

    def _detect_menhir_found(self, knowledge: Knowledge) -> list[MenhirFoundEvent]:
        if self._previous_knowledge is None:
            return []

        if self._previous_knowledge.arena.menhir_position != knowledge.arena.menhir_position:
            return [MenhirFoundEvent(knowledge.arena.menhir_position)]
        return []

    def _detect_weapon_found(self, knowledge: Knowledge) -> list[WeaponFoundEvent]:
        if self._previous_knowledge is None:
            return []

        new_weapons = knowledge.weapons.keys() - self._previous_knowledge.weapons.keys()
        return [WeaponFoundEvent(knowledge.weapons[weapon]) for weapon in new_weapons]

    def _detect_weapon_picked_up(self, knowledge: Knowledge) -> list[WeaponPickedUpEvent]:
        if self._previous_knowledge is None:
            return []

        if self._previous_knowledge.champion.weapon != knowledge.champion.weapon:
            return [WeaponPickedUpEvent(knowledge.champion.weapon)]
        return []

    def _detect_consumable_found(self, knowledge: Knowledge) -> list[ConsumableFoundEvent]:
        if self._previous_knowledge is None:
            return []

        new_consumables = knowledge.consumables.keys() - self._previous_knowledge.consumables.keys()
        return [ConsumableFoundEvent(knowledge.consumables[consumable]) for consumable in new_consumables]

    def _detect_losing_health(self, knowledge: Knowledge) -> list[LosingHealthEvent]:
        if self._previous_knowledge is None:
            return []

        damage = self._previous_knowledge.champion.health - knowledge.champion.health
        if damage > 0:
            return [LosingHealthEvent(damage)]
        return []

    def _detect_enemy_found(self, knowledge: Knowledge) -> list[EnemyFoundEvent]:
        # enemies can be detected multiple times, we trigger this event each time we see them
        new_enemies = []
        for enemy in knowledge.champions.values():
            if enemy.position in knowledge.visible_tiles \
                    and knowledge.visible_tiles[enemy.position].character is not None:
                new_enemies.append(enemy)
        return [EnemyFoundEvent(enemy) for enemy in new_enemies]

    def detect(self, knowledge: Knowledge) -> list[Event]:
        events = []
        events.extend(self._detect_menhir_found(knowledge))
        events.extend(self._detect_weapon_found(knowledge))
        events.extend(self._detect_consumable_found(knowledge))
        events.extend(self._detect_losing_health(knowledge))
        events.extend(self._detect_enemy_found(knowledge))

        self._previous_knowledge = deepcopy(knowledge)

        return events
