"""
Output naming rules for imported objects. No Blender dependency.
"""
import re

WHEEL_RE = re.compile(r"^chassis_wheel_([LR])_0*(\d+)$")

CRASH_TRACK_NAMES = ("chassis_track_crash_L", "chassis_track_crash_R")
CRASH_TRACK_DISPLAY_NAME = "tracks_crash"

VISUAL_NAME_MAP = {
    "hull": "hull_vis",
    "turret_01": "turret01",
    "turret_02": "turret02",
    "gun_02": "gun02",
    "gun_03": "gun03",
    "gun_05": "gun05",
    "chassis_track_L": "trackL",
    "chassis_track_R": "trackR",
}

ARMOR_GUN_PREFIX = "gun_mask"


def is_wheel(entity_name):
    return WHEEL_RE.match(entity_name) is not None


def is_hull(entity_name):
    return entity_name == "hull"


def is_crash_track(entity_name):
    return entity_name in CRASH_TRACK_NAMES


def visual_part_name(entity_name):
    """Display base name (without any _LODn suffix) for a visual-model part."""
    if entity_name in CRASH_TRACK_NAMES:
        return CRASH_TRACK_DISPLAY_NAME
    if entity_name in VISUAL_NAME_MAP:
        return VISUAL_NAME_MAP[entity_name]
    m = WHEEL_RE.match(entity_name)
    if m:
        side, num = m.groups()
        return f"wheel{side}{int(num)}"
    return entity_name


def armor_object_name(part_name, thickness_mm):
    mm = int(round(thickness_mm))
    if part_name == "hull":
        prefix = "armor_hull"
    elif part_name.startswith("turret_"):
        prefix = f"armor_{part_name}"
    elif part_name.startswith("gun_"):
        prefix = ARMOR_GUN_PREFIX
    else:
        prefix = f"armor_{part_name}"
    return f"{prefix}_{mm}"
