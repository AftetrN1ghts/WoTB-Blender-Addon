"""
Parses the vehicle definition XML (Data/XML/item_defs/vehicles/<nation>/<Internal>.xml)
for the part-mount offsets needed to assemble the CollisionMeshes armor parts
into one coherent tank.

Why this is needed: unlike the main visual .sc2 (whose part vertices are
already baked in final world-space, confirmed by direct inspection), the
CollisionMeshes armor parts for turret_* and gun_* are authored relative to
their own mount pivot - turret_01/02 relative to the hull's turret ring, and
each gun relative to its turret's gun cradle. Both offsets are given directly
in the vehicle XML:
    <hull><turretPositions><turret>X Y Z</turret></turretPositions></hull>
    <turrets0><turret_01>...<gunPosition>X Y Z</gunPosition>...

hull itself needs no offset (its own collision mesh is already in world space).
"""
import os
import xml.etree.ElementTree as ET

NATION_FOLDER_TO_XML_DIR = {
    "USSR": "ussr",
    "German": "germany",
    "France": "france",
    "GB": "uk",
    "Japan": "japan",
    "USA": "usa",
    "China": "china",
    "Other": "other",
}


def _parse_vec3(text):
    parts = text.split()
    return tuple(float(p) for p in parts[:3])


def find_vehicle_xml(data_root, nation_folder, internal_name):
    """data_root: path to the client's 'Data' folder."""
    xml_nation = NATION_FOLDER_TO_XML_DIR.get(nation_folder)
    if xml_nation is None:
        return None
    path = os.path.join(data_root, "XML", "item_defs", "vehicles", xml_nation, f"{internal_name}.xml")
    return path if os.path.isfile(path) else None


def parse_mount_offsets(xml_path):
    """
    Returns {
        "turret_ring": (x, y, z) or None,
        "turrets": {blitzPartName: {"gun_position": (x,y,z) or None}},
    }
    """
    result = {"turret_ring": None, "turrets": {}}
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return result
    root = tree.getroot()

    hull = root.find("hull")
    if hull is not None:
        tp = hull.find("turretPositions/turret")
        if tp is not None and tp.text:
            result["turret_ring"] = _parse_vec3(tp.text)

    for turrets_group in root.findall("./*"):
        if not turrets_group.tag.startswith("turrets"):
            continue
        for turret_el in list(turrets_group):
            # blitzPartName sits under this turret's own <blitz> child, not
            # as a direct child of the turret element itself.
            bpn_el = turret_el.find("blitz/blitzPartName")
            if bpn_el is None or not bpn_el.text:
                continue
            name = bpn_el.text.strip()
            gp_el = turret_el.find("gunPosition")
            gun_pos = _parse_vec3(gp_el.text) if gp_el is not None and gp_el.text else None
            result["turrets"][name] = {"gun_position": gun_pos}

    return result


def get_part_pivot(entity_name, mount_offsets):
    """
    The real in-game pivot (world-space translation, as used for rotation -
    turret traverse, gun elevation) for a part, straight from the vehicle
    XML. hull and everything else sits directly at the hull's own origin
    (0,0,0) - only turret_* (traverse ring) and gun_* (elevation trunnion,
    itself relative to the ring) have a meaningful separate pivot.
    """
    if not mount_offsets or entity_name == "hull":
        return (0.0, 0.0, 0.0)
    ring = mount_offsets.get("turret_ring") or (0.0, 0.0, 0.0)
    if entity_name.startswith("turret_"):
        return ring
    if entity_name.startswith("gun_"):
        gun_pos = None
        for turret_info in mount_offsets.get("turrets", {}).values():
            if turret_info.get("gun_position") is not None:
                gun_pos = turret_info["gun_position"]
                break
        gun_pos = gun_pos or (0.0, 0.0, 0.0)
        return tuple(ring[i] + gun_pos[i] for i in range(3))
    return (0.0, 0.0, 0.0)
