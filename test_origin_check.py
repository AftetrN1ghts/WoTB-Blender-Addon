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
props.lod0 = True
props.import_textures = False
props.import_armor = True
bpy.ops.wotb.import_tank()

for name in ["hull_vis", "turret01", "gun02", "wheelL1", "armor_hull_110", "armor_turret_01_150", "gun_mask_250"]:
    obj = bpy.data.objects.get(name)
    if obj is None:
        print(name, "-- NOT FOUND")
        continue
    world_v0 = obj.matrix_world @ obj.data.vertices[0].co
    print(f"{name:22s} location={tuple(round(x,3) for x in obj.location)}  "
          f"world_vertex0={tuple(round(x,3) for x in world_v0)}  "
          f"local_vertex0={tuple(round(x,3) for x in obj.data.vertices[0].co)}")
