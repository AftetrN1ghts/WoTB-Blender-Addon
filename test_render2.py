import sys, math
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

for o in bpy.data.objects:
    if o.type == 'MESH' and 'armor_thickness_mm' not in o:
        o.hide_render = True

cam_data = bpy.data.cameras.new("Cam")
cam_data.type = 'ORTHO'
cam_data.ortho_scale = 10
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = (-15, 0, 1)
cam.rotation_euler = (math.radians(90), 0, math.radians(-90))  # looking down +X, side profile (Y=length,Z=up)

sun_data = bpy.data.lights.new("Sun", type='SUN')
sun_data.energy = 3.0
sun = bpy.data.objects.new("Sun", sun_data)
sun.rotation_euler = (math.radians(60), 0, math.radians(20))
scene.collection.objects.link(sun)

scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
scene.render.resolution_x = 1200
scene.render.resolution_y = 500
scene.render.filepath = r"C:\ClassicOfBlitz\WoTB-Blender-Addon\render_armor_side.png"
scene.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(write_still=True)
print("done side view")

# top-down view too
cam.location = (0, 0, 15)
cam.rotation_euler = (0, 0, 0)
scene.render.filepath = r"C:\ClassicOfBlitz\WoTB-Blender-Addon\render_armor_top.png"
bpy.ops.render.render(write_still=True)
print("done top view")
