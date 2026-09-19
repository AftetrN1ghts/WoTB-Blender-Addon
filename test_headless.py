import sys
import bpy

ADDON_PARENT = r"C:\ClassicOfBlitz\WoTB-Blender-Addon"
if ADDON_PARENT not in sys.path:
    sys.path.insert(0, ADDON_PARENT)

import wotb_importer
wotb_importer.register()

scene = bpy.context.scene
props = scene.wotb_importer
props.tanks_root = r"C:\ClassicOfBlitz\WoTB\Data\3d\Tanks"
props.nation = "USSR"
props.tank_name = "IS-3"

res = bpy.ops.wotb.scan_tank()
print("scan result:", res, "max_lod:", props.max_lod, "n parts:", len(props.parts))
for item in props.parts:
    print("  part:", item.group_key, item.category, item.enabled)

props.lod0 = True
props.lod1 = False
props.import_textures = True
props.import_armor = True

res2 = bpy.ops.wotb.import_tank()
print("import result:", res2)

print("\n--- Collections ---")
for col in bpy.data.collections:
    print(col.name, "objects:", len(col.objects))

print("\n--- Objects with mesh data ---")
total_verts = 0
total_faces = 0
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        v = len(obj.data.vertices)
        f = len(obj.data.polygons)
        total_verts += v
        total_faces += f
        tag = ""
        if "armor_thickness_mm" in obj:
            tag = f"  armor_thickness_mm={obj['armor_thickness_mm']}"
        print(f"  {obj.name:40s} verts={v:5d} faces={f:5d} mats={[m.name for m in obj.data.materials]}{tag}")
print("TOTAL verts:", total_verts, "TOTAL faces:", total_faces)

out_path = r"C:\ClassicOfBlitz\WoTB-Blender-Addon\test_is3.blend"
bpy.ops.wm.save_as_mainfile(filepath=out_path)
print("\nSaved:", out_path)
