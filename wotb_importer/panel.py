import bpy
from bpy.types import Panel


class WOTB_PT_main(Panel):
    bl_idname = "WOTB_PT_main"
    bl_label = "WoT Blitz importer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "WoTB"

    def draw(self, context):
        layout = self.layout
        props = context.scene.wotb_importer

        col = layout.column()
        col.prop(props, "tanks_root")
        col.prop(props, "nation")
        col.prop(props, "tank_name")
        col.operator("wotb.scan_tank", icon='FILE_REFRESH')

        if not props.scanned_path:
            return

        layout.separator()
        box = layout.box()
        box.label(text="LODs (0 = most detailed)")
        row = box.row(align=True)
        lod_props = ["lod0", "lod1", "lod2", "lod3", "lod4", "lod5"]
        for i in range(props.max_lod + 1):
            row.prop(props, lod_props[i], toggle=True)

        layout.separator()
        box = layout.box()
        box.label(text="Modules")
        by_category = {}
        for item in props.parts:
            by_category.setdefault(item.category, []).append(item)
        for category, items in sorted(by_category.items()):
            sub = box.box()
            sub.label(text=category)
            for item in items:
                sub.prop(item, "enabled", text=item.group_key)

        layout.separator()
        box = layout.box()
        box.prop(props, "import_textures")
        box.prop(props, "skin_variant")
        box.prop(props, "import_armor")

        layout.separator()
        layout.operator("wotb.import_tank", icon='IMPORT')


classes = (WOTB_PT_main,)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
