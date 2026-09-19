import sys, math
import bpy

ADDON_PARENT = r"C:\ClassicOfBlitz\WoTB-Blender-Addon"
if ADDON_PARENT not in sys.path:
    sys.path.insert(0, ADDON_PARENT)

# clean default scene
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
props.import_textures = True
props.import_armor = True
bpy.ops.wotb.import_tank()

def frame_and_render(objects, out_path, ortho=False):
    for o in bpy.context.scene.objects:
        if o.type == 'CAMERA' or o.type == 'LIGHT':
            bpy.data.objects.remove(o, do_unlink=True)

    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    sun_data = bpy.data.lights.new("Sun", type='SUN')
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = (math.radians(55), 0, math.radians(35))
    scene.collection.objects.link(sun)

    minv = [1e9, 1e9, 1e9]
    maxv = [-1e9, -1e9, -1e9]
    for obj in objects:
        for corner in obj.bound_box:
            world = obj.matrix_world @ __import__("mathutils").Vector(corner)
            for i in range(3):
                minv[i] = min(minv[i], world[i])
                maxv[i] = max(maxv[i], world[i])
    center = [(minv[i] + maxv[i]) / 2 for i in range(3)]
    size = max(maxv[i] - minv[i] for i in range(3))

    dist = size * 1.8
    cam.location = (center[0] + dist * 0.7, center[1] - dist * 0.9, center[2] + dist * 0.5)
    direction = __import__("mathutils").Vector(center) - cam.location
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

    scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 700
    scene.render.filepath = out_path
    scene.render.image_settings.file_format = 'PNG'
    scene.display_settings.display_device = 'sRGB'
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)
    print("rendered:", out_path)

part_objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name != 'Cube'
             and 'Armor' not in (o.users_collection[0].name if o.users_collection else '')]
armor_objs = [o for o in bpy.data.objects if 'armor_thickness_mm' in o]

for o in bpy.data.objects:
    o.hide_render = True
for o in part_objs:
    o.hide_render = False
frame_and_render(part_objs, r"C:\ClassicOfBlitz\WoTB-Blender-Addon\render_parts.png")

for o in bpy.data.objects:
    o.hide_render = True
for o in armor_objs:
    o.hide_render = False
frame_and_render(armor_objs, r"C:\ClassicOfBlitz\WoTB-Blender-Addon\render_armor.png")

print("DONE")
