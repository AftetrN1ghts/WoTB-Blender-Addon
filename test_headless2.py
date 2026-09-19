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
props.nation = "Japan"
props.tank_name = "STA_1"

bpy.ops.wotb.scan_tank()
print("max_lod", props.max_lod, "parts", len(props.parts))

props.lod0 = True
props.import_textures = True
props.import_armor = True

bpy.ops.wotb.import_tank()

print("\n--- Images ---")
for img in bpy.data.images:
    print(" ", img.name, img.size[:], "source", img.source, "packed", img.packed_file is not None)

print("\n--- Materials with image textures ---")
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    for node in mat.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            print(f"  {mat.name} -> {node.image.name} ({node.image.size[0]}x{node.image.size[1]})")

out_path = r"C:\ClassicOfBlitz\WoTB-Blender-Addon\test_sta1.blend"
bpy.ops.wm.save_as_mainfile(filepath=out_path)
print("\nSaved:", out_path)
