import sys
import bpy

ADDON_PARENT = r"C:\ClassicOfBlitz\WoTB-Blender-Addon"
if ADDON_PARENT not in sys.path:
    sys.path.insert(0, ADDON_PARENT)

bpy.ops.wm.read_factory_settings(use_empty=True)

import wotb_importer
wotb_importer.register()

scene = bpy.context.scene
props = scene.wotb_importer
props.tanks_root = r"C:\ClassicOfBlitz\WoTB\Data\3d\Tanks"
props.nation = "USSR"
props.tank_name = "IS-3"

bpy.ops.wotb.scan_tank()
print("modules:")
for item in props.parts:
    print("  ", item.group_key, item.category, item.enabled)

props.lod0 = True
props.lod1 = True  # so chassis_track_crash (LOD1+) actually shows up
props.import_textures = False
props.import_armor = True
# enable Tracks_Crash explicitly for this test
for item in props.parts:
    if item.group_key == "Tracks_Crash":
        item.enabled = True

bpy.ops.wotb.import_tank()

print("\n--- Objects ---")
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    parent = obj.parent.name if obj.parent else None
    n_mat_slots = len(obj.data.materials)
    print(f"  {obj.name:30s} parent={parent!s:20s} verts={len(obj.data.vertices):5d} mat_slots={n_mat_slots}"
          + (f" armor_thickness_mm={obj['armor_thickness_mm']}" if 'armor_thickness_mm' in obj else ""))

out_path = r"C:\ClassicOfBlitz\WoTB-Blender-Addon\test_is3_renamed.blend"
bpy.ops.wm.save_as_mainfile(filepath=out_path)
print("Saved:", out_path)
