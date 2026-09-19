bl_info = {
    "name": "WoT Blitz (.sc2) importer",
    "description": "Import tank models, LODs, armor thickness and textures from WoT Blitz 0.4.x client files",
    "author": "built with Claude Code",
    "version": (0, 1, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > WoTB",
    "category": "Import-Export",
}

from . import props
from . import operators
from . import panel


def register():
    props.register()
    operators.register()
    panel.register()


def unregister():
    panel.unregister()
    operators.unregister()
    props.unregister()


if __name__ == "__main__":
    register()
