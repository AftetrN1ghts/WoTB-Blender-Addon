"""
Texture resolution and loading.

A material's 'textures' dict maps slot name -> logical path like
"images/IS-3.tex" or "CamouflageMasks/IS-3_CM.tex", relative to the tank's
own folder (Data/3d/Tanks/<Nation>/). The ".tex" file itself is a tiny
(~22 byte) DAVA TextureDescriptor - metadata only, NOT pixel data. The real
payload lives in a sibling file with the same basename and a different
extension (.pvr, .dx11.pvr, .dds, .dx11.dds, .tga, .png, ...), and in many
installs (including partial/streamed clients) that sibling file may simply
be missing - only the descriptor was downloaded.

PVR (PowerVR Texture v3) decoding is implemented here for uncompressed pixel
formats only (rgba8888 etc). Block-compressed formats (PVRTC, ETC, ASTC) are
detected and reported, not decoded - decompressing those from scratch is out
of scope; use Imagination's free PVRTexToolCLI to convert them to .png
up front if you need those textures.
"""
import os
import struct

CANDIDATE_SUFFIXES = [
    ".dx11.pvr", ".pvr",
    ".dx11.dds", ".dds",
    ".tga", ".png", ".jpg",
]

PVR_MAGIC = b"PVR\x03"

# channelType id -> (numpy-ish) not used; we only need bit depths for uncompressed.
_ASCII_CHANNELS = set(b"rgbalxds")


def resolve_texture_file(tank_dir, logical_path):
    """
    logical_path: e.g. "images/IS-3.tex" (as stored in the material).
    Returns absolute path to an existing pixel-data file, or None if only
    the descriptor (or nothing at all) is present.
    """
    rel = logical_path.replace("\\", "/")
    if rel.lower().endswith(".tex"):
        rel_base = rel[:-4]
    else:
        rel_base = rel
    base_path = os.path.normpath(os.path.join(tank_dir, rel_base))
    for suffix in CANDIDATE_SUFFIXES:
        candidate = base_path + suffix
        if os.path.isfile(candidate):
            return candidate
    return None


def descriptor_exists(tank_dir, logical_path):
    rel = logical_path.replace("\\", "/")
    path = os.path.normpath(os.path.join(tank_dir, rel))
    return os.path.isfile(path)


class UnsupportedPVR(RuntimeError):
    pass


def decode_pvr_uncompressed(path):
    """
    Decode an uncompressed PVR v3 file into (width, height, bytes) RGBA8 data.
    Raises UnsupportedPVR for block-compressed / unsupported formats.
    """
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != PVR_MAGIC:
        raise UnsupportedPVR(f"not a PVRv3 file: {path}")

    flags = struct.unpack_from("<I", data, 4)[0]
    pf_bytes = data[8:16]
    color_space, channel_type, height, width, depth, num_surfaces, num_faces, num_mipmaps = \
        struct.unpack_from("<IIIIIIII", data, 16)
    meta_size = struct.unpack_from("<I", data, 48)[0]
    pixel_start = 52 + meta_size

    channel_names = pf_bytes[0:4]
    bit_depths = pf_bytes[4:8]
    is_uncompressed = all(c in _ASCII_CHANNELS for c in channel_names if c != 0) and any(channel_names)

    if not is_uncompressed:
        fmt_id = struct.unpack_from("<Q", pf_bytes, 0)[0]
        raise UnsupportedPVR(
            f"block-compressed PVR pixel format (id={fmt_id}) in {path}; "
            "decode not implemented, convert with PVRTexToolCLI to .png first"
        )

    channels = [c for c in channel_names if c != 0]
    depths = list(bit_depths[:len(channels)])
    bits_per_pixel = sum(depths)
    if bits_per_pixel % 8 != 0:
        raise UnsupportedPVR(f"unsupported sub-byte packed PVR format in {path}")
    bytes_per_pixel = bits_per_pixel // 8

    npix = width * height
    raw = data[pixel_start:pixel_start + npix * bytes_per_pixel]
    if len(raw) < npix * bytes_per_pixel:
        raise UnsupportedPVR(f"truncated PVR pixel data in {path}")

    out = bytearray(npix * 4)
    chan_order = [chr(c) for c in channels]

    if bytes_per_pixel == 4 and depths == [8, 8, 8, 8] and chan_order == ["r", "g", "b", "a"]:
        out[:] = raw
    elif bytes_per_pixel == 3 and depths[:3] == [8, 8, 8]:
        for i in range(npix):
            out[i * 4 + 0] = raw[i * 3 + 0]
            out[i * 4 + 1] = raw[i * 3 + 1]
            out[i * 4 + 2] = raw[i * 3 + 2]
            out[i * 4 + 3] = 255
    elif bytes_per_pixel == 1 and chan_order == ["l"]:
        for i in range(npix):
            v = raw[i]
            out[i * 4:i * 4 + 4] = bytes((v, v, v, 255))
    elif bytes_per_pixel == 2 and chan_order == ["l", "a"]:
        for i in range(npix):
            l, a = raw[i * 2], raw[i * 2 + 1]
            out[i * 4:i * 4 + 4] = bytes((l, l, l, a))
    else:
        raise UnsupportedPVR(
            f"unhandled uncompressed PVR layout {chan_order}{depths} in {path}"
        )

    return width, height, bytes(out)


def load_texture_image(bpy, path, image_name):
    """
    Create (or reuse) a Blender image datablock for `path`.
    Returns the bpy.types.Image, or None if it couldn't be loaded/decoded.
    """
    existing = bpy.data.images.get(image_name)
    if existing is not None and existing.filepath == path:
        return existing

    ext = os.path.splitext(path)[1].lower()
    if ext == ".pvr":
        try:
            w, h, rgba = decode_pvr_uncompressed(path)
        except UnsupportedPVR as e:
            print(f"[WoTB importer] {e}")
            return None
        img = bpy.data.images.new(image_name, width=w, height=h, alpha=True)
        # Blender pixels are bottom-to-top float RGBA in [0,1]; PVR rows are top-to-bottom.
        flat = [0.0] * (w * h * 4)
        for y in range(h):
            src_row = (h - 1 - y) * w * 4
            dst_row = y * w * 4
            for x in range(w * 4):
                flat[dst_row + x] = rgba[src_row + x] / 255.0
        img.pixels.foreach_set(flat)
        img.pack()
        return img
    else:
        try:
            img = bpy.data.images.load(path, check_existing=True)
            img.name = image_name
            return img
        except RuntimeError as e:
            print(f"[WoTB importer] failed to load {path}: {e}")
            return None
