import os
import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty, IntProperty

from .armor import NATION_FOLDER_TO_PREFIX

# path -> scene_tree.TankModel, so enum callbacks / operators don't re-parse constantly.
MODEL_CACHE = {}


def _nation_items(self, context):
    props = context.scene.wotb_importer
    root = bpy.path.abspath(props.tanks_root)
    items = []
    if root and os.path.isdir(root):
        for folder in sorted(NATION_FOLDER_TO_PREFIX.keys()):
            if os.path.isdir(os.path.join(root, folder)):
                items.append((folder, folder, ""))
    return items or [("NONE", "<no tanks_root set>", "")]


def _tank_items(self, context):
    props = context.scene.wotb_importer
    root = bpy.path.abspath(props.tanks_root)
    nation = props.nation
    items = []
    nation_dir = os.path.join(root, nation) if root and nation else None
    if nation_dir and os.path.isdir(nation_dir):
        for fname in sorted(os.listdir(nation_dir)):
            full = os.path.join(nation_dir, fname)
            if os.path.isfile(full) and fname.lower().endswith(".sc2"):
                name = fname[:-4]
                items.append((name, name, full))
    return items or [("NONE", "<no tanks in this nation>", "")]


def _skin_items(self, context):
    from .materials import list_skin_variants
    props = context.scene.wotb_importer
    model = MODEL_CACHE.get(props.scanned_path)
    items = [("Default", "Default", "")]
    if model is not None:
        for part in model.parts:
            for batch in part.batches:
                variants = list_skin_variants(batch["material_id"], model.id_map)
                for v in variants:
                    if v and (v, v, "") not in items:
                        items.append((v, v, ""))
        if len(items) > 1:
            return items
    return items


class WOTB_PartToggle(PropertyGroup):
    group_key: StringProperty()
    category: StringProperty()
    enabled: BoolProperty(default=True)


class WOTB_ImporterProps(PropertyGroup):
    tanks_root: StringProperty(
        name="Tanks folder",
        description="Path to Data/3d/Tanks inside the WoT Blitz install",
        subtype='DIR_PATH',
    )
    nation: EnumProperty(name="Nation", items=_nation_items)
    tank_name: EnumProperty(name="Tank", items=_tank_items)

    scanned_path: StringProperty()  # absolute path of the currently-scanned file
    max_lod: IntProperty(default=0)

    lod0: BoolProperty(name="LOD0", default=True)
    lod1: BoolProperty(name="LOD1", default=False)
    lod2: BoolProperty(name="LOD2", default=False)
    lod3: BoolProperty(name="LOD3", default=False)
    lod4: BoolProperty(name="LOD4", default=False)
    lod5: BoolProperty(name="LOD5", default=False)

    import_textures: BoolProperty(name="Import textures", default=True)
    import_armor: BoolProperty(name="Import armor (with thickness)", default=True)

    skin_variant: EnumProperty(name="Skin", items=_skin_items)

    parts: CollectionProperty(type=WOTB_PartToggle)


classes = (WOTB_PartToggle, WOTB_ImporterProps)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.wotb_importer = bpy.props.PointerProperty(type=WOTB_ImporterProps)


def unregister():
    del bpy.types.Scene.wotb_importer
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
