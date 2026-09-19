"""
NMaterial resolution: walk the parentMaterialKey inheritance chain until we
find fxName/textures/properties (an "Instance-N" material has empty local
overrides and just points at its parent). Root materials with multiple
"skin" variants store them under configArchive_0, configArchive_1, ...
(configName e.g. "Default", "skin_<Tank>").

No Blender dependency - pure python.
"""
from .ka_format import as_id

SHADOW_HINTS = ("shadow", "shadowvolume")


def _is_empty(d):
    return not d


def resolve_material(mat_id, id_map, config_name=None):
    """
    Returns a dict: {materialName, fxName, textures, properties, is_shadow}
    or None if mat_id can't be resolved.
    config_name: preferred configName ("Default", "skin_XXX", ...); falls back
    to the first available config, or top-level fields for single-config materials.
    """
    seen = set()
    cur = as_id(mat_id)
    chain_name = None
    while cur is not None and cur not in seen:
        seen.add(cur)
        node = id_map.get(cur)
        if node is None:
            return None
        if chain_name is None:
            chain_name = node.get("materialName")

        fx = node.get("fxName")
        textures = node.get("textures") or {}
        properties = node.get("properties") or {}

        if fx or textures:
            return _finish(chain_name, fx, textures, properties)

        config_count = node.get("configCount")
        if config_count:
            configs = [v for k, v in node.items() if isinstance(k, str) and k.startswith("configArchive_")]
            chosen = None
            if config_name:
                for c in configs:
                    if c.get("configName") == config_name:
                        chosen = c
                        break
            if chosen is None and configs:
                for c in configs:
                    if c.get("configName") == "Default":
                        chosen = c
                        break
                if chosen is None:
                    chosen = configs[0]
            if chosen:
                return _finish(chain_name, chosen.get("fxName"), chosen.get("textures") or {},
                                chosen.get("properties") or {})

        cur = as_id(node.get("parentMaterialKey"))

    return None


def _finish(materialName, fx, textures, properties):
    fx_l = (fx or "").lower()
    is_shadow = any(h in fx_l for h in SHADOW_HINTS)
    return {
        "materialName": materialName,
        "fxName": fx,
        "textures": textures,
        "properties": properties,
        "is_shadow": is_shadow,
    }


def list_skin_variants(mat_id, id_map):
    """Walk up to the root material and list available configName values."""
    seen = set()
    cur = as_id(mat_id)
    while cur is not None and cur not in seen:
        seen.add(cur)
        node = id_map.get(cur)
        if node is None:
            return []
        if node.get("configCount"):
            names = []
            for k, v in node.items():
                if isinstance(k, str) and k.startswith("configArchive_") and isinstance(v, dict):
                    names.append(v.get("configName"))
            return names
        cur = as_id(node.get("parentMaterialKey"))
    return []
