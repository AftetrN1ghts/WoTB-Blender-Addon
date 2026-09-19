import os
import bpy
from bpy.types import Operator

from .scene_tree import TankModel
from .props import MODEL_CACHE
from . import build
from . import armor as armor_mod
from . import vehicle_xml


class WOTB_OT_scan_tank(Operator):
    bl_idname = "wotb.scan_tank"
    bl_label = "Scan tank"
    bl_description = "Parse the selected .sc2 file and list its parts/LODs/skins"

    def execute(self, context):
        props = context.scene.wotb_importer
        root = bpy.path.abspath(props.tanks_root)
        if props.nation in ("", "NONE") or props.tank_name in ("", "NONE"):
            self.report({'ERROR'}, "Pick a nation and a tank first")
            return {'CANCELLED'}

        path = os.path.join(root, props.nation, props.tank_name + ".sc2")
        if not os.path.isfile(path):
            self.report({'ERROR'}, f"File not found: {path}")
            return {'CANCELLED'}

        try:
            model = TankModel(path)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to parse {path}: {e}")
            return {'CANCELLED'}

        MODEL_CACHE.clear()
        MODEL_CACHE[path] = model
        props.scanned_path = path
        props.max_lod = model.max_lod

        props.parts.clear()
        for group_key, category, default_enabled in model.groups():
            item = props.parts.add()
            item.group_key = group_key
            item.category = category
            item.enabled = default_enabled

        self.report({'INFO'}, f"Scanned {props.tank_name}: {len(model.parts)} render parts, "
                               f"{len(props.parts)} modules, LOD0-{model.max_lod}")
        return {'FINISHED'}


class WOTB_OT_import_tank(Operator):
    bl_idname = "wotb.import_tank"
    bl_label = "Import tank"
    bl_description = "Build the selected parts/LODs/armor into the scene"

    def execute(self, context):
        props = context.scene.wotb_importer
        if not props.scanned_path:
            self.report({'ERROR'}, "Scan a tank first")
            return {'CANCELLED'}

        model = MODEL_CACHE.get(props.scanned_path)
        if model is None:
            try:
                model = TankModel(props.scanned_path)
                MODEL_CACHE[props.scanned_path] = model
            except Exception as e:
                self.report({'ERROR'}, f"Failed to (re)parse tank: {e}")
                return {'CANCELLED'}

        tank_dir = os.path.dirname(props.scanned_path)
        selected_groups = {p.group_key for p in props.parts if p.enabled}
        lod_flags = [props.lod0, props.lod1, props.lod2, props.lod3, props.lod4, props.lod5]
        selected_lods = {i for i, on in enumerate(lod_flags) if on and i <= props.max_lod}
        if not selected_lods:
            selected_lods = {0}

        root_name = props.tank_name
        root_collection = bpy.data.collections.new(root_name)
        context.scene.collection.children.link(root_collection)

        # Real in-game pivots (turret ring, gun trunnion) for both the visual
        # parts and the armor plates come from the same vehicle XML - read it
        # once and share it.
        tanks_root_abs = bpy.path.abspath(props.tanks_root)
        data_root = os.path.dirname(os.path.dirname(tanks_root_abs))  # .../Data/3d/Tanks -> .../Data
        xml_path = vehicle_xml.find_vehicle_xml(data_root, props.nation, props.tank_name)
        mount_offsets = vehicle_xml.parse_mount_offsets(xml_path) if xml_path else None
        if xml_path is None:
            self.report({'WARNING'}, "Vehicle XML not found - turret/gun origins will default to world origin")

        created_parts = build.import_parts(
            context, model, tank_dir, root_collection,
            selected_groups, selected_lods,
            props.import_textures, props.skin_variant,
            mount_offsets,
        )

        created_armor = 0
        if props.import_armor:
            collision_path = armor_mod.find_collision_file(
                tanks_root_abs, props.nation, props.tank_name
            )
            if collision_path:
                try:
                    plates = armor_mod.load_armor_plates(collision_path)
                    created_armor = build.import_armor(context, plates, root_collection, mount_offsets)
                except Exception as e:
                    self.report({'WARNING'}, f"Armor import failed: {e}")
            else:
                self.report({'WARNING'}, "No matching CollisionMeshes file found for this tank")

        self.report({'INFO'}, f"Imported {created_parts} part meshes"
                               + (f", {created_armor} armor plates" if props.import_armor else ""))
        return {'FINISHED'}


classes = (WOTB_OT_scan_tank, WOTB_OT_import_tank)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
