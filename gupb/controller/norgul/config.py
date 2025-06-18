# ------------------------------------
# Norgul hyperparameters - exploration
# ------------------------------------

EXPLORATION_MAX_TIME_DIFF = 50
EXPLORATION_TIME_FACTOR = 1.3
EXPLORATION_DISTANCE_FACTOR = 0.5


# ----------------------------------------
# Norgul hyperparameters - item collection
# ----------------------------------------

WEAPON_VALUES = {
    "bow": 0.8,
    "bow_unloaded": 0.8,
    "bow_loaded": 0.8,
    "knife": 1.0,
    "sword": 2.5,
    "axe": 5.0,
    "amulet": 0.0,
    "scroll": 0.0
}

POTION_VALUE = 2.0

COLLECTION_BASE_FACTOR = 1000.0
COLLECTION_DISTANCE_FACTOR = 0.9
COLLECTION_ENEMY_FACTOR = 0.33


# -------------------------------
# Norgul hyperparameters - combat
# -------------------------------

COMBAT_MAX_DIST = 50

COMBAT_THRESHOLD = 0.5

# Represents chances of weapon1 winning against weapon2
# NOTE: Use weapon1.name + "_vs_" + weapon2.name as a key
WEAPON_VS_WEAPON_CHANCES = {
    "bow_vs_bow": 0.5,
    "bow_vs_bow_unloaded": 0.5,
    "bow_vs_bow_loaded": 0.5,
    "bow_vs_knife": 0.33,
    "bow_vs_sword": 0.2,
    "bow_vs_axe": 0.05,
    "bow_vs_amulet": 0.9,
    "bow_vs_scroll": 0.99,

    "bow_unloaded_vs_bow": 0.5,
    "bow_unloaded_vs_bow_unloaded": 0.5,
    "bow_unloaded_vs_bow_loaded": 0.5,
    "bow_unloaded_vs_knife": 0.33,
    "bow_unloaded_vs_sword": 0.2,
    "bow_unloaded_vs_axe": 0.05,
    "bow_unloaded_vs_amulet": 0.9,
    "bow_unloaded_vs_scroll": 0.99,

    "bow_loaded_vs_bow": 0.5,
    "bow_loaded_vs_bow_unloaded": 0.5,
    "bow_loaded_vs_bow_loaded": 0.5,
    "bow_loaded_vs_knife": 0.33,
    "bow_loaded_vs_sword": 0.2,
    "bow_loaded_vs_axe": 0.05,
    "bow_loaded_vs_amulet": 0.9,
    "bow_loaded_vs_scroll": 0.99,

    "knife_vs_bow": 0.67,
    "knife_vs_bow_unloaded": 0.67,
    "knife_vs_bow_loaded": 0.67,
    "knife_vs_knife": 0.5,
    "knife_vs_sword": 0.1,
    "knife_vs_axe": 0.01,
    "knife_vs_amulet": 0.75,
    "knife_vs_scroll": 0.9,
    
    "sword_vs_bow": 0.8,
    "sword_vs_bow_unloaded": 0.8,
    "sword_vs_bow_loaded": 0.8,
    "sword_vs_knife": 0.9,
    "sword_vs_sword": 0.5,
    "sword_vs_axe": 0.33,
    "sword_vs_amulet": 0.95,
    "sword_vs_scroll": 0.99,

    "axe_vs_bow": 0.95,
    "axe_vs_bow_unloaded": 0.95,
    "axe_vs_bow_loaded": 0.95,
    "axe_vs_knife": 0.99,
    "axe_vs_sword": 0.67,
    "axe_vs_axe": 0.5,
    "axe_vs_amulet": 0.95,
    "axe_vs_scroll": 0.99,

    "amulet_vs_bow": 0.1,
    "amulet_vs_bow_unloaded": 0.1,
    "amulet_vs_bow_loaded": 0.1,
    "amulet_vs_knife": 0.25,
    "amulet_vs_sword": 0.05,
    "amulet_vs_axe": 0.05,
    "amulet_vs_amulet": 0.5,
    "amulet_vs_scroll": 0.99,

    "scroll_vs_bow": 0.01,
    "scroll_vs_bow_unloaded": 0.01,
    "scroll_vs_bow_loaded": 0.01,
    "scroll_vs_knife": 0.1,
    "scroll_vs_sword": 0.01,
    "scroll_vs_axe": 0.01,
    "scroll_vs_amulet": 0.01,
    "scroll_vs_scroll": 0.5
}