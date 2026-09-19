"""
High level model description built on top of ka_format: turns the raw
entity list into a list of importable "parts", each with its render
batches grouped by LOD tier. No Blender dependency.
"""
from .ka_format import read_sc2, build_entity_tree, flatten_parts, iter_components, as_id

WHEEL_L_PREFIX = "chassis_wheel_L"
WHEEL_R_PREFIX = "chassis_wheel_R"


def classify_part(name):
    """Return (group_key, category, default_enabled) for a part entity name."""
    if name is None:
        return ("Other", "Other", True)
    if name.startswith("HP_"):
        return ("Locators", "Locators", False)
    if name.startswith(WHEEL_L_PREFIX):
        return ("Wheels_L", "Chassis", True)
    if name.startswith(WHEEL_R_PREFIX):
        return ("Wheels_R", "Chassis", True)
    if name == "chassis_chassis_L":
        return ("Chassis_L", "Chassis", True)
    if name == "chassis_chassis_R":
        return ("Chassis_R", "Chassis", True)
    if name == "chassis_track_L":
        return ("Track_L", "Chassis", True)
    if name == "chassis_track_R":
        return ("Track_R", "Chassis", True)
    if name in ("chassis_track_crash_L", "chassis_track_crash_R"):
        return ("Tracks_Crash", "Chassis", False)
    if name == "hull":
        return ("Hull", "Hull", True)
    if name.startswith("turret_"):
        return (name, "Turret", True)
    if name.startswith("gun_"):
        return (name, "Gun", True)
    if name == "MaxScene":
        return (None, None, False)  # root, never a real part
    return (name, "Other", True)


def get_render_batches(entity):
    """
    Returns a list of dicts: {position, lod_index, switch_index, datasource, material_id, aabbox}
    for the entity's RenderComponent, or [] if it has none.
    """
    out = []
    for rc in iter_components(entity, "RenderComponent"):
        ro = rc.get("rc.renderObj") or {}
        batches = ro.get("ro.batches") or {}
        for pos, (bk, bv) in enumerate(sorted(batches.items())):
            if not isinstance(bv, dict):
                continue
            lod_index = ro.get(f"rb{pos}.lodIndex")
            switch_index = ro.get(f"rb{pos}.switchIndex")
            out.append({
                "position": pos,
                "lod_index": lod_index if lod_index is not None else 0,
                "switch_index": switch_index,
                "datasource": as_id(bv.get("rb.datasource")),
                "material_id": as_id(bv.get("rb.nmatname")),
                "aabbox": bv.get("rb.aabbox"),
            })
    return out


def get_lod_distances(entity):
    for lc in iter_components(entity, "LodComponent"):
        dist = lc.get("lc.loddist") or {}
        return [dist[k] for k in sorted(dist.keys())]
    return []


class Part:
    __slots__ = ("name", "entity", "group_key", "category", "default_enabled",
                 "batches", "lod_distances", "max_lod")

    def __init__(self, name, entity, group_key, category, default_enabled, batches, lod_distances):
        self.name = name
        self.entity = entity
        self.group_key = group_key
        self.category = category
        self.default_enabled = default_enabled
        self.batches = batches
        self.lod_distances = lod_distances
        self.max_lod = max((b["lod_index"] for b in batches), default=0)


class TankModel:
    def __init__(self, path):
        self.raw = read_sc2(path)
        self.id_map = self.raw["id_map"]
        roots = build_entity_tree(self.raw["entities"])
        flat = flatten_parts(roots)
        self.parts = []
        for ent in flat:
            group_key, category, default_enabled = classify_part(ent.get("name"))
            if group_key is None:
                continue
            batches = get_render_batches(ent)
            if not batches:
                continue
            lod_dist = get_lod_distances(ent)
            self.parts.append(Part(ent.get("name"), ent, group_key, category,
                                    default_enabled, batches, lod_dist))
        self.max_lod = max((p.max_lod for p in self.parts), default=0)

    def groups(self):
        """Ordered unique (group_key, category, default_enabled) tuples."""
        seen = {}
        for p in self.parts:
            if p.group_key not in seen:
                seen[p.group_key] = (p.group_key, p.category, p.default_enabled)
        return list(seen.values())
