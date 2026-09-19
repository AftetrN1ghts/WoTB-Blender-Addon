"""
Reader for DAVA Engine's KeyedArchive (v1) binary format and the outer
SceneFileV2 (.sc2) container, as used by WoT Blitz 0.4.7.

No Blender dependency - pure python, safe to unit test standalone.

Format (reverse engineered from this client's own files; low level KA1
encoding confirmed against the public docs of Pyogenics/SCPG-reverse-engineering):

KeyedArchive v1:
    magic       b"KA"
    version     uint16 LE   (== 1)
    itemCount   uint32 LE
    itemCount * (keyEntry, valueEntry), each entry = uint8 typeTag + payload

SC2 container:
    magic           b"SFV2"
    version         uint32 LE
    rootNodeCount   uint32 LE
    KA              "version tags" (usually empty in this client version)
    uint32          descriptor size
    uint8           file type (0=Scene, 1=Model)
    ...             (descriptor size - 1) extra bytes, skipped
    uint32          dataNodeCount
    dataNodeCount * KA1   -- the DataNode pool: PolygonGroup / NMaterial, etc,
                             each identified by its own "#id" field (int64)
    (until EOF)     further KA1 blocks, back to back -- the Entity/scene tree,
                             flattened as a pre-order walk. Each Entity KA has
                             "#childrenCount" telling how many of the following
                             flattened blocks are its descendants.
"""
import struct

TYPE_NONE = 0
TYPE_BOOLEAN = 1
TYPE_INT32 = 2
TYPE_FLOAT = 3
TYPE_STRING = 4
TYPE_WIDE_STRING = 5
TYPE_BYTE_ARRAY = 6
TYPE_UINT32 = 7
TYPE_KEYED_ARCHIVE = 8
TYPE_INT64 = 9
TYPE_UINT64 = 10
TYPE_VECTOR2 = 11
TYPE_VECTOR3 = 12
TYPE_VECTOR4 = 13
TYPE_MATRIX2 = 14
TYPE_MATRIX3 = 15
TYPE_MATRIX4 = 16
TYPE_COLOR = 17
TYPE_FASTNAME = 18
TYPE_AABBOX3 = 19
TYPE_FILEPATH = 20
TYPE_FLOAT64 = 21
TYPE_INT8 = 22
TYPE_UINT8 = 23
TYPE_INT16 = 24
TYPE_UINT16 = 25
TYPE_ARRAY = 27


class KAFormatError(RuntimeError):
    pass


class Reader:
    __slots__ = ("buf", "pos")

    def __init__(self, buf, pos=0):
        self.buf = buf
        self.pos = pos

    def eof(self):
        return self.pos >= len(self.buf)

    def bytes(self, n):
        v = self.buf[self.pos:self.pos + n]
        if len(v) != n:
            raise EOFError(f"wanted {n} bytes at {self.pos}, got {len(v)}")
        self.pos += n
        return v

    def u8(self):
        return self.bytes(1)[0]

    def i16(self):
        v = struct.unpack_from("<h", self.buf, self.pos)[0]
        self.pos += 2
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.buf, self.pos)[0]
        self.pos += 2
        return v

    def i32(self):
        v = struct.unpack_from("<i", self.buf, self.pos)[0]
        self.pos += 4
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.buf, self.pos)[0]
        self.pos += 4
        return v

    def i64(self):
        v = struct.unpack_from("<q", self.buf, self.pos)[0]
        self.pos += 8
        return v

    def u64(self):
        v = struct.unpack_from("<Q", self.buf, self.pos)[0]
        self.pos += 8
        return v

    def f32(self):
        v = struct.unpack_from("<f", self.buf, self.pos)[0]
        self.pos += 4
        return v

    def f64(self):
        v = struct.unpack_from("<d", self.buf, self.pos)[0]
        self.pos += 8
        return v

    def str(self, length):
        return self.bytes(length).decode("utf-8", errors="replace")


def read_value(r: Reader, type_tag: int):
    if type_tag == TYPE_NONE:
        return None
    if type_tag == TYPE_BOOLEAN:
        return bool(r.u8())
    if type_tag == TYPE_INT32:
        return r.i32()
    if type_tag == TYPE_FLOAT:
        return r.f32()
    if type_tag in (TYPE_STRING, TYPE_WIDE_STRING, TYPE_FASTNAME, TYPE_FILEPATH):
        length = r.u32()
        return r.str(length)
    if type_tag == TYPE_BYTE_ARRAY:
        length = r.u32()
        return r.bytes(length)
    if type_tag == TYPE_UINT32:
        return r.u32()
    if type_tag == TYPE_KEYED_ARCHIVE:
        length = r.u32()
        sub = r.bytes(length)
        return read_ka1(Reader(sub))
    if type_tag == TYPE_INT64:
        return r.i64()
    if type_tag == TYPE_UINT64:
        return r.u64()
    if type_tag == TYPE_VECTOR2:
        return (r.f32(), r.f32())
    if type_tag == TYPE_VECTOR3:
        return (r.f32(), r.f32(), r.f32())
    if type_tag == TYPE_VECTOR4:
        return (r.f32(), r.f32(), r.f32(), r.f32())
    if type_tag == TYPE_MATRIX2:
        return tuple(r.f32() for _ in range(4))
    if type_tag == TYPE_MATRIX3:
        return tuple(r.f32() for _ in range(9))
    if type_tag == TYPE_MATRIX4:
        return tuple(r.f32() for _ in range(16))
    if type_tag == TYPE_COLOR:
        return (r.f32(), r.f32(), r.f32(), r.f32())
    if type_tag == TYPE_AABBOX3:
        mn = (r.f32(), r.f32(), r.f32())
        mx = (r.f32(), r.f32(), r.f32())
        return (mn, mx)
    if type_tag == TYPE_FLOAT64:
        return r.f64()
    if type_tag == TYPE_INT8:
        return struct.unpack("<b", r.bytes(1))[0]
    if type_tag == TYPE_UINT8:
        return r.u8()
    if type_tag == TYPE_INT16:
        return r.i16()
    if type_tag == TYPE_UINT16:
        return r.u16()
    if type_tag == TYPE_ARRAY:
        length = r.u32()
        arr = []
        for _ in range(length):
            t = r.u8()
            arr.append(read_value(r, t))
        return arr
    raise KAFormatError(f"Unknown KA1 type tag {type_tag} at offset {r.pos}")


def read_ka1(r: Reader):
    magic = r.bytes(2)
    if magic != b"KA":
        raise KAFormatError(f"bad KA magic {magic!r} at {r.pos - 2}")
    version = r.u16()
    if version != 1:
        raise KAFormatError(f"expected KA version 1, got {version} at {r.pos - 2}")
    item_count = r.u32()
    archive = {}
    for _ in range(item_count):
        kt = r.u8()
        key = read_value(r, kt)
        vt = r.u8()
        value = read_value(r, vt)
        archive[key] = value
    return archive


def as_id(value):
    """Normalize a raw '#id' / 'rb.datasource' / 'rb.nmatname' style field to an int."""
    if isinstance(value, (bytes, bytearray)):
        return int.from_bytes(value, "little")
    return value


def read_sc2(path):
    with open(path, "rb") as f:
        data = f.read()
    r = Reader(data)
    magic = r.bytes(4)
    if magic != b"SFV2":
        raise KAFormatError(f"not an SFV2 file: {magic!r}")
    version = r.u32()
    root_node_count = r.u32()
    version_tags = read_ka1(r)
    desc_size = r.u32()
    desc_start = r.pos
    file_type = r.u8()
    r.pos = desc_start + desc_size
    data_node_count = r.u32()

    data_nodes = []
    for i in range(data_node_count):
        data_nodes.append(read_ka1(r))

    entities = []
    while not r.eof():
        start = r.pos
        try:
            entities.append(read_ka1(r))
        except (KAFormatError, EOFError):
            r.pos = start
            break

    id_map = {}
    for node in data_nodes:
        id_map[as_id(node.get("#id"))] = node

    return {
        "path": path,
        "version": version,
        "root_node_count": root_node_count,
        "file_type": file_type,
        "data_nodes": data_nodes,
        "entities": entities,
        "id_map": id_map,
        "bytes_total": len(data),
        "bytes_consumed": r.pos,
    }


def build_entity_tree(entities):
    """
    Reconstruct parent/child structure from the flat pre-order list using
    each entity's '#childrenCount'. Returns the list of top-level (root's
    direct children) entities, each with a '_children' list attached.
    """
    def consume(index):
        ent = entities[index]
        n_children = ent.get("#childrenCount", 0) or 0
        index += 1
        children = []
        for _ in range(n_children):
            child, index = consume(index)
            children.append(child)
        ent["_children"] = children
        return ent, index

    roots = []
    i = 0
    while i < len(entities):
        ent, i = consume(i)
        roots.append(ent)
    return roots


def iter_components(entity, typename=None):
    comps = entity.get("components", {})
    for k, c in comps.items():
        if not isinstance(c, dict):
            continue
        if typename is None or c.get("comp.typename") == typename:
            yield c


def flatten_parts(entities):
    """Depth-first flatten of the entity tree into a single list of 'part' entities
    (any entity that isn't purely structural)."""
    out = []

    def walk(ent):
        out.append(ent)
        for c in ent.get("_children", []):
            walk(c)

    for e in entities:
        walk(e)
    return out
