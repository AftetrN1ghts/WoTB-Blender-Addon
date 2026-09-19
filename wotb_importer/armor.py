"""
Armor / collision mesh handling.

Armor shape+thickness lives in a separate file:
    Data/3d/Tanks/CollisionMeshes/<nation-prefix>-<InternalName>.sc2
keyed by the tank's *internal* short name (matches the visual model's own
filename) and a lowercase nation prefix that does NOT always match the
visual-model folder name (e.g. folder "GB" -> prefix "uk", "German" ->
"germany", "USSR" -> "ussr", "Japan" -> "japan" unchanged).

Structurally a CollisionMeshes file is just another SC2: DataNode pool of
PolygonGroup + NMaterial, and a flat Entity list (hull / turret_01 /
turret_02 / gun_02 / gun_03 / gun_05, one render batch each, no LODs).

Confirmed empirically: for CollisionMeshes PolygonGroups (vertexFormat 15 -
VERTEX|NORMAL|TEXCOORD0|COLOR), the trailing 4-byte 'COLOR' slot of every
vertex is actually a raw float32 = armor thickness in millimeters at that
point, uniform across all 3 vertices of every triangle (0 counter-examples
across every part checked). Grouping triangles by that value reconstructs
the individual armor plates without needing the vehicle XML at all.
"""
import os
from .ka_format import read_sc2, build_entity_tree, flatten_parts, as_id
from .scene_tree import get_render_batches
from .polygon_group import decode_polygon_group, group_triangles_by_thickness

NATION_FOLDER_TO_PREFIX = {
    "USSR": "ussr",
    "German": "germany",
    "France": "france",
    "GB": "uk",
    "Japan": "japan",
    "USA": "usa",
    "China": "china",
    "Other": "other",
}


def find_collision_file(tanks_root, nation_folder, internal_name):
    prefix = NATION_FOLDER_TO_PREFIX.get(nation_folder)
    if prefix is None:
        return None
    candidate = os.path.join(tanks_root, "CollisionMeshes", f"{prefix}-{internal_name}.sc2")
    return candidate if os.path.isfile(candidate) else None


class ArmorPlate:
    __slots__ = ("part_name", "thickness_mm", "positions", "normals", "triangles")

    def __init__(self, part_name, thickness_mm, positions, normals, triangles):
        self.part_name = part_name
        self.thickness_mm = thickness_mm
        self.positions = positions
        self.normals = normals
        self.triangles = triangles


def load_armor_plates(collision_file_path):
    """
    Returns list[ArmorPlate], one per contiguous same-thickness triangle group,
    per part (hull/turret_01/turret_02/gun_*) found in the collision file.

    Positions are left exactly as decoded - i.e. relative to that part's own
    in-game pivot (world-space for hull, turret-ring-relative for turret_*,
    gun-trunnion-relative for gun_*). The build step places each resulting
    object with `obj.location = vehicle_xml.get_part_pivot(...)`, so the
    mesh data and the object's origin both end up matching the game exactly,
    instead of baking the pivot into the vertices.
    """
    raw = read_sc2(collision_file_path)
    id_map = raw["id_map"]
    roots = build_entity_tree(raw["entities"])
    parts = flatten_parts(roots)

    plates = []
    for ent in parts:
        name = ent.get("name")
        if not name:
            continue
        for batch in get_render_batches(ent):
            pg = id_map.get(batch["datasource"])
            if pg is None or pg.get("##name") != "PolygonGroup":
                continue
            decoded = decode_polygon_group(pg, want_armor_thickness=True)
            if decoded["thickness"] is None:
                continue
            groups = group_triangles_by_thickness(decoded)
            for thickness_mm, tris in sorted(groups.items()):
                plates.append(ArmorPlate(
                    part_name=name,
                    thickness_mm=thickness_mm,
                    positions=decoded["positions"],
                    normals=decoded["normals"],
                    triangles=tris,
                ))
    return plates
