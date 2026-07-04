from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BfsCost:
    account_hp: bool
    mist: bool
    fire: bool
    enemy_range: bool
    enemy_blocked: bool

    @classmethod
    def full(cls) -> "BfsCost":
        return cls(
            account_hp=True,
            mist=True,
            fire=True,
            enemy_range=True,
            enemy_blocked=True,
        )

    @classmethod
    def distance(cls) -> "BfsCost":
        return cls(
            account_hp=False,
            mist=False,
            fire=False,
            enemy_range=False,
            enemy_blocked=True,
        )

    @classmethod
    def reachability(cls) -> "BfsCost":
        return cls(
            account_hp=False,
            mist=False,
            fire=False,
            enemy_range=False,
            enemy_blocked=False,
        )
