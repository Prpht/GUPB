from typing import Optional
from copy import deepcopy

from gupb.model.characters import PENALISED_IDLE_TIME
from gupb.controller.batman.knowledge.knowledge import (
    Knowledge,
    ArenaKnowledge,
    TileKnowledge,
    ChampionKnowledge,
    WeaponKnowledge,
    ConsumableKnowledge,
)


class Event:
    @property
    def name(self):
        raise NotImplementedError()


class MenhirFoundEvent(Event):
    name = "menhir_found"
    __match_args__ = ("position",)

    def __init__(self, position):
        self.position = position


class WeaponFoundEvent(Event):
    name = "weapon_found"
    __match_args__ = ("weapon",)

    def __init__(self, weapon: WeaponKnowledge):
        self.weapon = weapon


class WeaponPickedUpEvent(Event):
    name = "weapon_picked_up"
    __match_args__ = ("weapon_name",)

    def __init__(self, weapon_name: str):
        self.weapon_name = weapon_name


class ConsumableFoundEvent(Event):
    name = "consumable_found"
    __match_args__ = ("consumable",)

    def __init__(self, consumable: ConsumableKnowledge):
        self.consumable = consumable


class LosingHealthEvent(Event):
    name = "losing_health"
    __match_args__ = ("damage",)

    def __init__(self, damage: int):
        self.damage = damage


class EnemyFoundEvent(Event):
    name = "enemy_found"
    __match_args__ = ("champion",)

    def __init__(self, champion: ChampionKnowledge):
        self.champion = champion


class IdlePenaltyEvent(Event):
    name = "idle_penalty"
    __match_args__ = ("episodes_to_penalty",)

    def __init__(self, episodes_to_penalty: int):
        self.episodes_to_penalty = episodes_to_penalty


class EventDetector:
    def __init__(self):
        self._previous_knowledge: Optional[Knowledge] = None
        self._idle_episodes = 0

    def _detect_menhir_found(self, knowledge: Knowledge) -> list[MenhirFoundEvent]:
        if self._previous_knowledge is None:
            return []

        if (
            self._previous_knowledge.arena.menhir_position
            != knowledge.arena.menhir_position
        ):
            return [MenhirFoundEvent(knowledge.arena.menhir_position)]
        return []

    def _detect_weapon_found(self, knowledge: Knowledge) -> list[WeaponFoundEvent]:
        if self._previous_knowledge is None:
            return []

        new_weapons = knowledge.weapons.keys() - self._previous_knowledge.weapons.keys()
        return [WeaponFoundEvent(knowledge.weapons[weapon]) for weapon in new_weapons]

    def _detect_weapon_picked_up(
        self, knowledge: Knowledge
    ) -> list[WeaponPickedUpEvent]:
        if self._previous_knowledge is None:
            return []

        if self._previous_knowledge.champion.weapon != knowledge.champion.weapon:
            return [WeaponPickedUpEvent(knowledge.champion.weapon)]
        return []

    def _detect_consumable_found(
        self, knowledge: Knowledge
    ) -> list[ConsumableFoundEvent]:
        if self._previous_knowledge is None:
            return []

        consumables = []
        for position, consumable in knowledge.consumables.items():
            if (
                position in knowledge.visible_tiles
                and knowledge.visible_tiles[position].consumable is not None
            ):
                consumables.append(consumable)

        return [ConsumableFoundEvent(consumable) for consumable in consumables]

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
            if (
                enemy.position in knowledge.visible_tiles
                and enemy.name != "Batman"
                and knowledge.visible_tiles[enemy.position].character is not None
                and knowledge.visible_tiles[enemy.position].character.controller_name
                == enemy.name
            ):
                new_enemies.append(enemy)
        return [EnemyFoundEvent(enemy) for enemy in new_enemies]

    def _detect_idle_penalty(self, knowledge: Knowledge) -> list[IdlePenaltyEvent]:
        if self._previous_knowledge is None:
            return [IdlePenaltyEvent(episodes_to_penalty=PENALISED_IDLE_TIME)]

        if (
            self._previous_knowledge.champion.position == knowledge.champion.position
            and self._previous_knowledge.champion.facing == knowledge.champion.facing
        ):
            self._idle_episodes += 1
        else:
            self._idle_episodes = 0

        return [
            IdlePenaltyEvent(
                episodes_to_penalty=PENALISED_IDLE_TIME - self._idle_episodes
            )
        ]

    def detect(self, knowledge: Knowledge) -> list[Event]:
        events = []
        events.extend(self._detect_menhir_found(knowledge))
        events.extend(self._detect_weapon_found(knowledge))
        events.extend(self._detect_consumable_found(knowledge))
        events.extend(self._detect_losing_health(knowledge))
        events.extend(self._detect_enemy_found(knowledge))
        events.extend(self._detect_idle_penalty(knowledge))

        self._previous_knowledge = deepcopy(knowledge)

        return events
