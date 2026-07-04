_BASE_DAMAGE: dict[str, int] = {
    "knife": 2,
    "sword": 2,
    "axe": 3,
    "bow": 3,
    "amulet": 2,
    "scroll": 0,
}

_WEAPON_TO_INT: dict[str, int] = {
    "knife": 0,
    "bow_unloaded": 1,
    "bow_loaded": 2,
    "axe": 9,
    "sword": 10,
    "amulet": 11,
}

_DEFAULT_DAMAGE: int = 2
_SCROLL_CHARGES: int = 5
_NON_SCROLL_CHARGES: int = 100


def base_name(weapon: str) -> str:
    return weapon.split("_")[0].lower()


def parse_weapon(weapon: str) -> tuple[str, int]:
    if weapon.startswith("scroll"):
        parts = weapon.split("_")
        charges = int(parts[1]) if len(parts) > 1 else _SCROLL_CHARGES
        return "scroll", charges
    return weapon, _NON_SCROLL_CHARGES


def weapon_to_int(weapon: str) -> int:
    name, charges = parse_weapon(weapon)
    if name == "scroll":
        return 3 + charges
    return _WEAPON_TO_INT.get(name, 0)


def attack_damage(weapon: str) -> int:
    name, charges = parse_weapon(weapon)
    if name == "scroll":
        return 3 if charges > 0 else 0
    if name == "bow_unloaded":
        return 0
    return _BASE_DAMAGE.get(base_name(name), _DEFAULT_DAMAGE)


def weapon_max_range(weapon: str) -> int:
    name, charges = parse_weapon(weapon)
    if name == "scroll":
        return 1 if charges > 0 else 0
    if name == "knife":
        return 1
    if name == "axe":
        return 2
    if name == "sword":
        return 3
    if name == "amulet":
        return 4
    if "bow" in name:
        return 50
    return 1
