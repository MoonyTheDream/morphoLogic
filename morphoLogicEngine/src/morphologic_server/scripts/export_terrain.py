"""A script to export terrain data from the database to a GLB file.
Run with `morphologic export-terrain --output <output_file_path>`."""

import numpy as np
import trimesh

from pathlib import Path

from morphologic_server import logger

from morphologic_server.config import ServerSettings
from morphologic_server.db.engine import create_sessionmaker
from morphologic_server.db.memory import Memory
from morphologic_server.db.models import Base, Terrain
from morphologic_server.terrain_palette import LINEAR_PALETTE


def _zup_to_gltf_yup(verts: np.ndarray) -> np.ndarray:
    """Rotate vertex positions from our Z-up world to glTF +Y-up.

    Inverse of the importer's `_gltf_yup_to_zup`: (x, y, z) → (x, z, -y).
    Without this, Blender's glTF importer (which assumes Y-up) reads our
    Z-axis as forward and shows the terrain edge-on.
    """
    return np.column_stack([verts[:, 0], verts[:, 2], -verts[:, 1]])


def _build_arrays(terrains: list[Terrain]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert a list of Terrain objects into vertex, face, and color arrays
    suitable for creating a Trimesh mesh."""

    tile_index:    dict[tuple[int, int], int] = {}
    vertices:       list[tuple[float, float, float]] = []
    colors:         list[tuple[int, int, int, int]] = []

    for t in terrains:
        p = t.location
        key = (round(p.x), round(p.y))
        tile_index[key] = len(vertices)
        vertices.append((p.x, p.y, p.z))
        colors.append(LINEAR_PALETTE[t.type])
        
    faces: list[tuple[int, int, int]] = []
    for (x, y), i_bl in tile_index.items():
        i_br = tile_index.get((x + 1, y))
        i_tl = tile_index.get((x,     y + 1))
        i_tr = tile_index.get((x + 1, y + 1))
        if i_br is None or i_tl is None or i_tr is None:
            continue

        faces.append((i_bl, i_br, i_tr))
        faces.append((i_bl, i_tr, i_tl))

    return (
        np.array(vertices, dtype=np.float64),
        np.array(faces,    dtype=np.int64) if faces else np.empty((0, 3), dtype=np.int64),
        np.array(colors,   dtype=np.uint8),
    )
    
async def export_terrain(output: Path) -> None:
    """Fetch all terrain data from the database, convert it to a mesh, and
    export it as a 3D model file."""
    
    settings = ServerSettings()
    sessionmaker = create_sessionmaker(settings.DB_ADDRESS)
    Base._sessionmaker = sessionmaker
    memory = Memory(sessionmaker)
    
    terrains = await memory.get_all_terrain_data()
    logger.info("Exporting %d terrain tiles to '%s'...", len(terrains), output)
    verts, faces, colors = _build_arrays(terrains)
    verts = _zup_to_gltf_yup(verts)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, vertex_colors=colors, process=False)
    mesh.export(output)
    logger.info("Exported %d tiles (%d faces) → %s", len(terrains), len(faces), output)
    