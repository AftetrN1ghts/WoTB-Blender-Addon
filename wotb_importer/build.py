"""
Blender-side mesh/object/collection/material construction.
Everything bpy-dependent lives in this module.
"""
import os
import bpy
import mathutils

from .polygon_group import decode_polygon_group
from .materials import resolve_material
from .textures import resolve_texture_file, load_texture_image
from .ka_format import iter_components
from . import naming
from . import vehicle_xml

# Simple blue(thin) -> red(thick) gradient for quick visual reading of armor plates.
_ARMOR_COLOR_STOPS = [
    (0, (0.1, 0.3, 1.0)),
    (30, (0.1, 0.8, 0.9)),
    (60, (0.2, 0.9, 0.2)),
    (100, (0.95, 0.85, 0.1)),
    (150, (0.95, 0.45, 0.05)),
    (250, (0.9, 0.05, 0.05)),
]

_WHEEL_DISPLAY_RE = __import__("re").compile(r"^wheel[LR]\d+$")


def _armor_color(mm):
    stops = _ARMOR_COLOR_STOPS
    if mm <= stops[0][0]:
        return stops[0][1]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t0 <= mm <= t1:
            f = (mm - t0) / max(t1 - t0, 1e-6)
            return tuple(c0[i] + (c1[i] - c0[i]) * f for i in range(3))
    return stops[-1][1]


def get_or_create_collection(name, parent):
    col = bpy.data.collections.get(name)
    if col is None or col.name not in parent.children:
        # Always create a fresh one for a clean import (avoid stale-name reuse across tanks).
        col = bpy.data.collections.new(name)
        parent.children.link(col)
    return col


def _world_matrix_for_entity(entity):
    for tc in iter_components(entity, "TransformComponent"):
        return tc.get("tc.worldMatrix")
    return None


def _transform_positions(positions, world_matrix_16):
    if not world_matrix_16 or len(world_matrix_16) != 16:
        return positions
    m = world_matrix_16
    if all(m[i] == (1.0 if i in (0, 5, 10, 15) else 0.0) for i in range(16)):
        return positions  # identity, nothing to do
    # DAVA stores row-major matrices with translation in the last row
    # (DirectX-style); build as 4 rows then transpose for Blender's
    # column-vector convention.
    rows = [m[0:4], m[4:8], m[8:12], m[12:16]]
    mat = mathutils.Matrix(rows)
    mat.transpose()
    return [tuple(mat @ mathutils.Vector(p)) for p in positions]


def _shift_positions(positions, pivot):
    if pivot == (0.0, 0.0, 0.0):
        return positions
    return [(p[0] - pivot[0], p[1] - pivot[1], p[2] - pivot[2]) for p in positions]


def _get_placeholder_material():
    mat = bpy.data.materials.get("WoTB_NoMaterial")
    if mat is None:
        mat = bpy.data.materials.new("WoTB_NoMaterial")
        mat.use_nodes = True
    return mat


def _make_merged_mesh_object(name, chunks, flip_v=True):
    """chunks: list of {positions, uv0, triangles, material (bpy.types.Material or None)}."""
    mesh = bpy.data.meshes.new(name)
    all_positions = []
    all_uv = []
    all_faces = []
    face_material_index = []
    materials_ordered = []
    slot_of_material = {}

    for chunk in chunks:
        base = len(all_positions)
        all_positions.extend(chunk["positions"])
        uv0 = chunk.get("uv0")
        all_uv.extend(uv0 if uv0 else [(0.0, 0.0)] * len(chunk["positions"]))

        mat = chunk.get("material") or _get_placeholder_material()
        slot = slot_of_material.get(mat.name)
        if slot is None:
            slot = len(materials_ordered)
            materials_ordered.append(mat)
            slot_of_material[mat.name] = slot

        for tri in chunk["triangles"]:
            all_faces.append(tuple(base + i for i in tri))
            face_material_index.append(slot)

    mesh.from_pydata(all_positions, [], all_faces)
    mesh.update(calc_edges=True)

    for mat in materials_ordered:
        mesh.materials.append(mat)
    for poly, slot in zip(mesh.polygons, face_material_index):
        poly.material_index = slot

    uv_layer = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        for loop_index, vert_index in zip(poly.loop_indices, poly.vertices):
            u, v = all_uv[vert_index]
            uv_layer.data[loop_index].uv = (u, 1.0 - v if flip_v else v)

    mesh.shade_smooth()
    return bpy.data.objects.new(name, mesh)


def get_or_create_material(mat_id, id_map, tank_dir, import_textures, skin_variant, cache):
    cache_key = (mat_id, skin_variant, import_textures)
    if cache_key in cache:
        return cache[cache_key]

    resolved = resolve_material(mat_id, id_map, config_name=skin_variant)
    if resolved is None:
        cache[cache_key] = None
        return None

    mat_name = f"WoTB_{resolved['materialName']}"
    bl_mat = bpy.data.materials.get(mat_name)
    if bl_mat is None:
        bl_mat = bpy.data.materials.new(mat_name)
        bl_mat.use_nodes = True

    if import_textures:
        albedo_path = resolved["textures"].get("albedo")
        if albedo_path:
            tex_file = resolve_texture_file(tank_dir, albedo_path)
            if tex_file:
                img = load_texture_image(bpy, tex_file, os.path.splitext(os.path.basename(tex_file))[0])
                if img is not None:
                    bsdf = bl_mat.node_tree.nodes.get("Principled BSDF")
                    if bsdf is not None:
                        tex_node = bl_mat.node_tree.nodes.new("ShaderNodeTexImage")
                        tex_node.image = img
                        bl_mat.node_tree.links.new(bsdf.inputs["Base Color"], tex_node.outputs["Color"])

    cache[cache_key] = bl_mat
    return bl_mat


def import_parts(context, model, tank_dir, root_collection, selected_groups,
                  selected_lods, import_textures, skin_variant, mount_offsets=None):
    """
    model: scene_tree.TankModel
    selected_groups: set of group_key strings to import
    selected_lods: set of int lod tiers to import
    mount_offsets: vehicle_xml.parse_mount_offsets() result, or None

    Parts are renamed per `naming.visual_part_name` and merged into one object
    per (display name, LOD) - this is what turns the two crash-track entities
    into a single 'tracks_crash' object. Wheels end up parented to the hull
    object of the same LOD once everything is built.

    Each part's vertices come out of decode_polygon_group already baked in
    final world-space, so its object would otherwise get its origin dumped
    at world (0,0,0) regardless of where the mesh sits. Instead of an
    arbitrary bounding-box recenter, every part is shifted back by its real
    in-game pivot (vehicle_xml.get_part_pivot: the turret ring for turret_*,
    the gun trunnion for gun_*, world origin - i.e. no shift - for
    everything hull-relative) and the object's `location` is set to that
    same pivot, so the origin lands exactly where the game puts it.
    """
    material_cache = {}
    buckets = {}  # (display_base, lod) -> {"chunks": [...], "pivot": (x,y,z)}

    for part in model.parts:
        if part.group_key not in selected_groups:
            continue
        entity_name = part.entity.get("name")
        display_base = naming.visual_part_name(entity_name)
        world_matrix = _world_matrix_for_entity(part.entity)
        pivot = vehicle_xml.get_part_pivot(entity_name, mount_offsets)

        for batch in part.batches:
            lod = batch["lod_index"] if batch["lod_index"] is not None and batch["lod_index"] >= 0 else 0
            if lod not in selected_lods:
                continue
            pg = model.id_map.get(batch["datasource"])
            if pg is None or pg.get("##name") != "PolygonGroup":
                continue

            resolved_mat = resolve_material(batch["material_id"], model.id_map, config_name=skin_variant)
            if resolved_mat is not None and resolved_mat["is_shadow"]:
                continue  # skip shadow-volume proxy batches

            decoded = decode_polygon_group(pg)
            if not decoded["positions"] or not decoded["triangles"]:
                continue

            positions = _transform_positions(decoded["positions"], world_matrix)
            positions = _shift_positions(positions, pivot)
            bl_mat = get_or_create_material(batch["material_id"], model.id_map, tank_dir,
                                             import_textures, skin_variant, material_cache)

            key = (display_base, lod)
            bucket = buckets.setdefault(key, {"chunks": [], "pivot": pivot})
            bucket["chunks"].append({
                "positions": positions,
                "uv0": decoded["uv0"],
                "triangles": decoded["triangles"],
                "material": bl_mat,
            })

    lod_collections = {}
    hull_objects = {}
    wheel_objects = {}
    created = 0

    for (display_base, lod), bucket in buckets.items():
        obj_name = display_base if lod == 0 else f"{display_base}_LOD{lod}"
        obj = _make_merged_mesh_object(obj_name, bucket["chunks"])
        if bucket["pivot"] != (0.0, 0.0, 0.0):
            obj.location = bucket["pivot"]

        lod_col = lod_collections.get(lod)
        if lod_col is None:
            lod_col = get_or_create_collection(f"LOD{lod}", root_collection)
            lod_collections[lod] = lod_col
        lod_col.objects.link(obj)
        created += 1

        if display_base == "hull_vis":
            hull_objects[lod] = obj
        elif _WHEEL_DISPLAY_RE.match(display_base):
            wheel_objects.setdefault(lod, []).append(obj)

    # Wheels live under the hull.
    for lod, wheels in wheel_objects.items():
        hull_obj = hull_objects.get(lod)
        if hull_obj is None:
            continue
        for w in wheels:
            w.parent = hull_obj
            w.matrix_parent_inverse = hull_obj.matrix_world.inverted()

    return created


def import_armor(context, plates, root_collection, mount_offsets=None):
    """
    Armor plate positions come straight out of decode_polygon_group without
    any shifting (see armor.load_armor_plates) - i.e. already relative to
    that part's own in-game pivot. So placing the object just means setting
    its `location` to that same pivot (vehicle_xml.get_part_pivot); no mesh
    transform needed, unlike the visual parts.
    """
    armor_col = get_or_create_collection("Armor", root_collection)
    material_cache = {}
    created = 0

    for plate in plates:
        verts_used = sorted({i for tri in plate.triangles for i in tri})
        remap = {old: new for new, old in enumerate(verts_used)}
        positions = [plate.positions[i] for i in verts_used]
        faces = [tuple(remap[i] for i in tri) for tri in plate.triangles]

        mm = plate.thickness_mm
        obj_name = naming.armor_object_name(plate.part_name, mm)
        mesh = bpy.data.meshes.new(obj_name)
        mesh.from_pydata(positions, [], faces)
        mesh.update(calc_edges=True)
        mesh.shade_flat()

        obj = bpy.data.objects.new(obj_name, mesh)
        pivot = vehicle_xml.get_part_pivot(plate.part_name, mount_offsets)
        if pivot != (0.0, 0.0, 0.0):
            obj.location = pivot
        obj["armor_thickness_mm"] = float(mm)
        obj["armor_part"] = plate.part_name

        mat_name = f"WoTB_Armor_{int(round(mm))}"
        bl_mat = material_cache.get(mat_name)
        if bl_mat is None:
            bl_mat = bpy.data.materials.get(mat_name)
            if bl_mat is None:
                bl_mat = bpy.data.materials.new(mat_name)
                bl_mat.use_nodes = True
                bsdf = bl_mat.node_tree.nodes.get("Principled BSDF")
                if bsdf is not None:
                    r, g, b = _armor_color(mm)
                    bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
            material_cache[mat_name] = bl_mat
        mesh.materials.append(bl_mat)

        armor_col.objects.link(obj)
        created += 1

    return created
