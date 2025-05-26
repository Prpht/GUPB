from dataclasses import dataclass, field
from typing import List
import math

@dataclass(slots=True)
class Settings:
    better_weapons: List[str] = field(default_factory=lambda: ["amulet", "axe", "sword", "bow_loaded", "bow_unloaded", "scroll"])
    aggression_turn_dst: int = 3
    mist_escape_limit: int = 15
    menhir_wandering: int = 3
    menhir_ignore: bool = False
    mist_ignore: bool = False
    ignore_possible_attack_opportunity: bool = False
    disable_hidden_spots: bool = False
    ignore_weapon: bool = False
    true_random: bool = False
    ignore_potion: bool = False
    bow_disables_aggro: bool = True
    explore: bool = False
    attack_when_in_path: bool = True
    auto_load_bow: bool = False
    menhir_turns_off_exploration: bool = True
    vanishing_forest: bool = False

    priority_hide: float = 900
    priority_weapon_go_back: float = -1001  # unintentional dropped weapon
    priority_menhir: float = -1000
    priority_mist_with_menhir: float = 500
    priority_mist_no_menhir: float = 0
    priority_mist_no_menhir_time_multiplier: float = 0.1
    priority_potion: float = 190
    priority_potion_time_multiplier: float = 0.1
    priority_weapon_no_scroll: float = -2000
    priority_weapon_better: float = 200
    priority_explore: float = 1001
    priority_killer_goals_normal: float = 100
    priority_killer_goals_normal_time_multiplier: float = 0.01
    priority_killer_goals_menhir: float = -10000
    priority_killer_goals_menhir_time_multiplier: float = 0.01
    priority_killer_goals_path: float = -100 
    priority_killer_goals_path_time_multiplier: float = 0.01
    priority_attack_position_dst_multiplier: float = 0.001
    priority_potion_dst_multiplier: float = 1
