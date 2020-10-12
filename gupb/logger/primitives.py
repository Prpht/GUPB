from dataclasses import dataclass
from enum import Enum
from typing import List

from dataclasses_json import dataclass_json, DataClassJsonMixin

from gupb.model.coordinates import Coords


class LogSeverity(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ChampionSpawnedReport(DataClassJsonMixin):
    controller_name: str
    coords: Coords
    facing_value: Coords


@dataclass(frozen=True)
class ChampionPickedWeaponReport(DataClassJsonMixin):
    controller_name: str
    weapon_name: str


@dataclass(frozen=True)
class ChampionFacingReport(DataClassJsonMixin):
    controller_name: str
    facing_value: Coords


@dataclass(frozen=True)
class ChampionEnteredTileReport(DataClassJsonMixin):
    controller_name: str
    tile_coords: Coords


@dataclass(frozen=True)
class ChampionDamagedByMistReport(DataClassJsonMixin):
    controller_name: str
    damage: int


@dataclass(frozen=True)
class ChampionDamagedByWeaponCutReport(DataClassJsonMixin):
    controller_name: str
    damage: int


@dataclass(frozen=True)
class ChampionPickedActionReport(DataClassJsonMixin):
    controller_name: str
    action_name: str


@dataclass(frozen=True)
class ChampionAttackReport(DataClassJsonMixin):
    controller_name: str
    weapon_name: str


@dataclass(frozen=True)
class ChampionWoundsReport(DataClassJsonMixin):
    controller_name: str
    wounds: int
    rest_health: int


@dataclass(frozen=True)
class ChampionDeathReport(DataClassJsonMixin):
    controller_name: str


@dataclass(frozen=True)
class MenhirSpawnedReport(DataClassJsonMixin):
    position: Coords


@dataclass(frozen=True)
class MistRadiusReducedReport(DataClassJsonMixin):
    mist_radius: int


@dataclass(frozen=True)
class EpisodeStartReport(DataClassJsonMixin):
    episode_number: int


@dataclass(frozen=True)
class GameStartReport(DataClassJsonMixin):
    game_number: int


@dataclass(frozen=True)
class LastManStandingReport(DataClassJsonMixin):
    controller_name: str


@dataclass(frozen=True)
class ControllerScoreReport(DataClassJsonMixin):
    controller_name: str
    score: int


@dataclass(frozen=True)
class RandomArenaPickReport(DataClassJsonMixin):
    arena_name: str


@dataclass(frozen=True)
class FinalScoresReport(DataClassJsonMixin):
    scores: List[ControllerScoreReport]


