"""Import terrain into the DB from a 3D mesh file (.glb or .obj).

Run with `morphologic import-terrain --input <path>`.

The mesh is loaded via trimesh; every vertex is snapped to the 1m integer
grid; multiple vertices in one (x,y) cell are mean-reduced; vertex colours
are nearest-matched against the canonical TerrainType palette. The Terrain
table is then atomically wiped and replaced, and every GameObject's Z is
shifted by the local terrain delta so existing objects track the new surface.

Authoring workflow in Blender (no add-on needed):
    Add → Mesh → Plane → Edit Mode → subdivide → Sculpt Mode → push hills
    → Vertex Paint Mode → paint with the 4 TerrainType colours
    → File → Export → glTF 2.0 (enable 'Vertex Colors' under Data → Mesh).
"""

from pathlib import Path

import numpy as np
import trimesh

from morphologic_server import logger
from morphologic_server.config import ServerSettings
from morphologic_server.db.engine import create_sessionmaker
from morphologic_server.db.memory import Memory
from morphologic_server.db.models import Base
from morphologic_server.terrain_palette import (
    TerrainTile,
    color_to_terrain_type,
)


# A cell whose mean colour lies further than this from every palette entry
# triggers a per-cell warning. Distance is in uint8 RGB units; max is ~442.
OFF_PALETTE_WARN_THRESHOLD = 80.0


def _gltf_yup_to_zup(verts: np.ndarray) -> np.ndarray:
    """Rotate vertex positions from glTF's +Y-up to our Z-up world.

    Blender's default glTF export emits Y-up; trimesh loads as-is. Inverse
    rotation is +90° around X: (x, y, z) → (x, -z, y). Apply unconditionally
    here; if a file is already Z-up (e.g. OBJ exported with axis overrides),
    disable Blender's "+Y Up" checkbox on export and remove this call.
    """
    return np.column_stack([verts[:, 0], -verts[:, 2], verts[:, 1]])


def _fill_gaps(tiles: list[TerrainTile]) -> list[TerrainTile]:
    """Densify a sparse tile set onto its bounding box.

    Iterates: every empty cell with at least one 8-neighbour gets the mean Z
    and majority TerrainType of those neighbours, then those cells become
    sources for further fills next pass. Stops when no new cell can be filled.
    Cells with no neighbours after convergence (true voids outside the dense
    region) stay empty.
    """
    if not tiles:
        return tiles

    by_xy: dict[tuple[int, int], TerrainTile] = {(t.x, t.y): t for t in tiles}
    xs = [t.x for t in tiles]
    ys = [t.y for t in tiles]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    while True:
        new_fills: dict[tuple[int, int], TerrainTile] = {}
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                if (x, y) in by_xy:
                    continue
                neighbours = [
                    by_xy[(x + dx, y + dy)]
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                    if (dx, dy) != (0, 0) and (x + dx, y + dy) in by_xy
                ]
                if not neighbours:
                    continue
                z = int(round(sum(n.z for n in neighbours) / len(neighbours)))
                type_counts: dict = {}
                for n in neighbours:
                    type_counts[n.type] = type_counts.get(n.type, 0) + 1
                mode_type = max(type_counts, key=type_counts.get)
                new_fills[(x, y)] = TerrainTile(x, y, z, mode_type)
        if not new_fills:
            break
        by_xy.update(new_fills)

    return list(by_xy.values())


def _load_mesh(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load `path` and return (vertices, vertex_colors) as numpy arrays.

    Raises ValueError with a hint if the file is not a single mesh or has
    no per-vertex colours.
    """
    loaded = trimesh.load(path, force="mesh")
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError(f"{path} did not yield a single triangle mesh.")

    verts = np.asarray(loaded.vertices, dtype=np.float64)

    try:
        colors = np.asarray(loaded.visual.vertex_colors, dtype=np.uint8)
    except (AttributeError, ValueError) as exc:
        raise ValueError(
            f"{path} has no per-vertex colours. In Blender's glTF export "
            f"dialog, enable 'Vertex Colors' under Data → Mesh."
        ) from exc

    if colors.shape != (len(verts), 4):
        raise ValueError(
            f"vertex_colors shape {colors.shape} doesn't match vertex count "
            f"{len(verts)}."
        )

    return verts, colors


def _aggregate_cells(
    verts: np.ndarray, colors: np.ndarray
) -> tuple[list[TerrainTile], int]:
    """Bin vertices onto the 1m integer grid, mean-reduce Z and colour per
    cell, nearest-match each cell's colour to a TerrainType.

    Returns `(tiles, off_palette_warnings)` where off_palette_warnings is
    the number of cells whose colour distance to its nearest TerrainType
    exceeded `OFF_PALETTE_WARN_THRESHOLD` (and were logged).
    """
    xy_snapped = np.round(verts[:, :2]).astype(np.int64)

    cells: dict[tuple[int, int], list[int]] = {}
    for i, (x, y) in enumerate(xy_snapped):
        cells.setdefault((int(x), int(y)), []).append(i)

    tiles: list[TerrainTile] = []
    warnings = 0
    for (x, y), indices in cells.items():
        idx_arr = np.array(indices)
        z = int(round(float(verts[idx_arr, 2].mean())))
        rgba_mean = colors[idx_arr].mean(axis=0)
        ttype, dist = color_to_terrain_type(rgba_mean)
        if dist > OFF_PALETTE_WARN_THRESHOLD:
            warnings += 1
            logger.warning(
                "Cell (%d, %d) painted off-palette (distance %.1f → matched %s)",
                x, y, dist, ttype.name,
            )
        tiles.append(TerrainTile(x, y, z, ttype))

    return tiles, warnings


async def import_terrain(input_path: Path) -> None:
    """Load `input_path`, aggregate to tiles, replace Terrain, shift objects."""
    settings = ServerSettings()
    sessionmaker = create_sessionmaker(settings.DB_ADDRESS)
    Base._sessionmaker = sessionmaker
    memory = Memory(sessionmaker)

    logger.info("Loading mesh from '%s'...", input_path)
    verts, colors = _load_mesh(input_path)
    verts = _gltf_yup_to_zup(verts)
    logger.info("Mesh loaded: %d vertices (Y-up → Z-up applied).", len(verts))

    tiles, off_palette = _aggregate_cells(verts, colors)
    logger.info("Aggregated → %d unique tiles.", len(tiles))

    tiles = _fill_gaps(tiles)
    logger.info("Densified → %d tiles after gap-fill.", len(tiles))

    tiles_inserted, objects_shifted = await memory.replace_terrain_and_shift_objects(tiles)

    logger.info(
        "Import complete: inserted %d tiles, shifted %d objects, %d off-palette cells.",
        tiles_inserted, objects_shifted, off_palette,
    )
