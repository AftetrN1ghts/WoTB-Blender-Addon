"""
Decode a PolygonGroup DataNode (vertex/index buffers) into plain python
lists. No Blender dependency.

Vertex format is a bitmask (DataNode key 'vertexFormat'); channels are packed
back-to-back in the order below with the sizes noted. This order was verified
empirically against this client's own files (both regular render meshes and
CollisionMeshes armor meshes) - it is NOT simply "process flags in numeric
bit order", the on-disk layout puts TEXCOORD0 before COLOR.

Regular visible meshes seen in this client use format 395
(VERTEX|NORMAL|TEXCOORD0|TANGENT|BINORMAL) or 3 (VERTEX|NORMAL).
CollisionMeshes (armor) meshes use format 15 (VERTEX|NORMAL|TEXCOORD0|COLOR),
where the last 4 bytes of the vertex (nominally the 'COLOR' slot) are
repurposed to store a single float32: the armor thickness in mm for that
vertex. This was verified directly: for every triangle in every collision
mesh checked, all 3 vertices share byte-identical thickness, and the set of
distinct values matches the <armor> block of the vehicle's XML definition.
"""
import struct

VERTEX = 1
NORMAL = 1 << 1
COLOR = 1 << 2
TEXCOORD0 = 1 << 3
TEXCOORD1 = 1 << 4
TEXCOORD2 = 1 << 5
TEXCOORD3 = 1 << 6
TANGENT = 1 << 7
BINORMAL = 1 << 8
HARD_JOINTINDEX = 1 << 9
PIVOT4 = 1 << 10
FLEXIBILITY = 1 << 12
ANGLE_SIN_COS = 1 << 13
JOINTINDEX = 1 << 14
JOINTWEIGHT = 1 << 15
CUBETEXCOORD0 = 1 << 16
CUBETEXCOORD1 = 1 << 17
CUBETEXCOORD2 = 1 << 18
CUBETEXCOORD3 = 1 << 19

# (flag, size in bytes, on-disk order)
_CHANNEL_ORDER = [
    (VERTEX, 12),
    (NORMAL, 12),
    (TEXCOORD0, 8),
    (COLOR, 4),
    (TEXCOORD1, 8),
    (TEXCOORD2, 8),
    (TEXCOORD3, 8),
    (TANGENT, 12),
    (BINORMAL, 12),
    (HARD_JOINTINDEX, 4),
    (CUBETEXCOORD0, 12),
    (CUBETEXCOORD1, 12),
    (CUBETEXCOORD2, 12),
    (CUBETEXCOORD3, 12),
    (PIVOT4, 16),
    (FLEXIBILITY, 4),
    (ANGLE_SIN_COS, 8),
    (JOINTINDEX, 16),
    (JOINTWEIGHT, 16),
]


class VertexLayout:
    def __init__(self, fmt):
        self.fmt = fmt
        self.offsets = {}
        stride = 0
        for flag, size in _CHANNEL_ORDER:
            if fmt & flag:
                self.offsets[flag] = stride
                stride += size
        self.stride = stride

    def has(self, flag):
        return flag in self.offsets


def decode_polygon_group(pg, want_armor_thickness=False):
    """
    pg: a DataNode dict with ##name == 'PolygonGroup'.
    Returns dict with 'positions', 'normals', 'uv0', 'triangles' (index triplets),
    and optionally 'thickness' (per-vertex float, only meaningful for
    CollisionMeshes files when want_armor_thickness=True).
    """
    fmt = pg["vertexFormat"]
    layout = VertexLayout(fmt)
    vcount = pg["vertexCount"]
    vbuf = pg["vertices"]
    stride = layout.stride
    if stride == 0 or vcount == 0:
        stride = len(vbuf) // max(vcount, 1)

    positions = [None] * vcount
    normals = [None] * vcount if layout.has(NORMAL) else None
    uv0 = [None] * vcount if layout.has(TEXCOORD0) else None
    thickness = [None] * vcount if want_armor_thickness else None

    for i in range(vcount):
        base = i * stride
        if layout.has(VERTEX):
            o = base + layout.offsets[VERTEX]
            positions[i] = struct.unpack_from("<fff", vbuf, o)
        if normals is not None:
            o = base + layout.offsets[NORMAL]
            normals[i] = struct.unpack_from("<fff", vbuf, o)
        if uv0 is not None:
            o = base + layout.offsets[TEXCOORD0]
            uv0[i] = struct.unpack_from("<ff", vbuf, o)
        if thickness is not None and layout.has(COLOR):
            o = base + layout.offsets[COLOR]
            thickness[i] = struct.unpack_from("<f", vbuf, o)[0]

    ibuf = pg["indices"]
    idxfmt = pg["indexFormat"]
    icount = pg["indexCount"]
    if idxfmt == 0:
        indices = list(struct.unpack_from(f"<{icount}H", ibuf, 0))
    elif idxfmt == 1:
        indices = list(struct.unpack_from(f"<{icount}I", ibuf, 0))
    else:
        raise ValueError(f"unknown indexFormat {idxfmt}")

    prim_type = pg.get("rhi_primitiveType", 1)
    if prim_type == 2:  # triangle strip
        triangles = []
        for i in range(2, len(indices)):
            a, b, c = indices[i - 2], indices[i - 1], indices[i]
            if a == b or b == c or a == c:
                continue
            if i % 2 == 0:
                triangles.append((a, b, c))
            else:
                triangles.append((b, a, c))
    else:  # triangle list (default)
        triangles = [tuple(indices[i:i + 3]) for i in range(0, len(indices) - 2, 3)]

    return {
        "positions": positions,
        "normals": normals,
        "uv0": uv0,
        "thickness": thickness,
        "triangles": triangles,
    }


def group_triangles_by_thickness(decoded, ndigits=2):
    """
    Group a decoded CollisionMeshes PolygonGroup's triangles by their
    (uniform, per-triangle) armor thickness value.
    Returns dict: rounded_thickness_mm -> list of triangles (vertex index triplets).
    """
    thickness = decoded["thickness"]
    groups = {}
    for tri in decoded["triangles"]:
        vals = {round(thickness[i], ndigits) for i in tri}
        # Use the value of the first vertex; in practice all 3 match exactly.
        t = round(thickness[tri[0]], ndigits)
        groups.setdefault(t, []).append(tri)
    return groups
