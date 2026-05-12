"""Shared palette and data shapes for terrain ↔ mesh conversion.

Used by the exporter (scripts/export_terrain.py) and the importer
(scripts/import_terrain.py). Colours are uint8 RGBA in [0, 255]. The palette
defines exactly one colour per TerrainType — this is the canonical mapping
in both directions.
"""

from typing import NamedTuple

import numpy as np

from morphologic_server.db.models import TerrainType


TERRAIN_COLORS: dict[TerrainType, tuple[int, int, int, int]] = {
    TerrainType.SOIL:  (140,  90,  50, 255),  # #8C5A32
    TerrainType.SAND:  (230, 205, 130, 255),  # #E6CD82
    TerrainType.ROCK:  (140, 140, 140, 255),  # #8C8C8C
    TerrainType.WATER: ( 50, 115, 215, 255),  # #3273D7
}


class TerrainTile(NamedTuple):
    """Candidate tile produced by the importer's aggregation step,
    before being written to the DB."""
    x: int
    y: int
    z: int
    type: TerrainType


class ImportStats(NamedTuple):
    """Summary of an import run — surfaced in the CLI log and useful for tests."""
    tiles_inserted: int
    objects_shifted: int
    off_palette_warnings: int


def _srgb_to_linear_uint8(c_uint8: int) -> float:
    """Convert an sRGB-encoded uint8 channel value to a linear uint8 (as float).

    glTF 2.0 defines COLOR_0 vertex attributes as linear. Blender's colour
    picker accepts sRGB hex but stores/exports the linearised value, so the
    bytes in the file don't match our sRGB palette unless we linearise it
    here. Both ends (importer matching, exporter writing) use linear values;
    TERRAIN_COLORS stays sRGB only as a human-readable definition that
    mirrors Blender's hex input.
    """
    v = c_uint8 / 255.0
    linear = v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return linear * 255


# Linear-space palette, used for round-trip-correct matching against glTF data.
LINEAR_PALETTE: dict[TerrainType, tuple[int, int, int, int]] = {
    ttype: (
        round(_srgb_to_linear_uint8(r)),
        round(_srgb_to_linear_uint8(g)),
        round(_srgb_to_linear_uint8(b)),
        a,
    )
    for ttype, (r, g, b, a) in TERRAIN_COLORS.items()
}

_PALETTE_TYPES: list[TerrainType] = list(LINEAR_PALETTE.keys())
_PALETTE_RGB: np.ndarray = np.array(
    [rgba[:3] for rgba in LINEAR_PALETTE.values()], dtype=np.float64
)


def color_to_terrain_type(rgba) -> tuple[TerrainType, float]:
    """Nearest TerrainType to ``rgba`` by Euclidean distance in linear RGB space.

    Alpha is ignored. ``rgba`` is expected to be linear-encoded uint8 — i.e.
    raw bytes from a glTF COLOR_0 buffer. Distance is in uint8 units; max
    possible is ``sqrt(3 * 255**2) ≈ 442``. Callers can use it to warn about
    off-palette colours.
    """
    rgb = np.asarray(rgba, dtype=np.float64)[:3]
    dists = np.linalg.norm(_PALETTE_RGB - rgb, axis=1)
    idx = int(np.argmin(dists))
    return _PALETTE_TYPES[idx], float(dists[idx])
