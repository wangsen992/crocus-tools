"""
OpenFOAM VTK post-processing and visualization tools.

Generates animations from surface output files.
"""

import numpy as np
import pandas as pd
from pathlib import Path
import pyvista
import argparse
from concurrent.futures import ProcessPoolExecutor
from typing import Optional


pyvista.OFF_SCREEN = True
pyvista.set_jupyter_backend('static')

DEFAULT_START_TIME = pd.to_datetime("2024-07-01 00:00:00")


class SurfaceDirectoryChecker:
    """Check if directory conforms to OpenFOAM postProcessing structure."""

    @staticmethod
    def is_valid(surf_dir: Path) -> bool:
        """Surface dir should have time step directories containing surface files."""
        try:
            time_dirs = [d for d in surf_dir.iterdir() if d.is_dir()]
            if not time_dirs:
                return False
            return any(
                (d / "surface_file.vtp").exists()
                for d in time_dirs
                for _ in d.glob("*.vtp")
            )
        except:
            return False


def surface_file_gen(
    surf_dir: Path,
    fname: str,
    max_files: Optional[int] = None
):
    """
    Generate (time, mesh) tuples from surface files.

    Args:
        surf_dir: Path to postProcessing/surfaces directory
        fname: Surface file name (e.g., "two_meter_terrain.vtp")
        max_files: Maximum number of files to process

    Yields:
        Tuple of (time_value, pyvista mesh)
    """
    if max_files is None:
        max_files = len(list(surf_dir.iterdir()))

    count = 0
    for d in sorted(surf_dir.iterdir(), key=lambda f: float(f.name)):
        if count >= max_files:
            break
        file_path = d / fname
        if file_path.exists():
            yield float(d.name), pyvista.read(file_path)
        count += 1


def generate_timestamp(time_value: float, start_time: pd.Timestamp) -> str:
    """Convert time value to ISO timestamp string."""
    return (start_time + pd.to_timedelta(time_value, unit='s')) \
        .isoformat(sep=' ', timespec='seconds')


def animate_surface(
    surface_dir: str,
    fname: str,
    vname: str,
    movie_name: Optional[str] = None,
    max_files: Optional[int] = None,
    scalar_bar_args: Optional[dict] = None,
    mesh_kwargs: Optional[dict] = None,
    cmap: str = "viridis",
    clim: Optional[tuple] = None,
    framerate: int = 30
):
    """
    Generate animation from surface files.

    Args:
        surface_dir: Path to surfaces directory
        fname: Surface file name
        vname: Scalar variable name to plot
        movie_name: Output movie filename (MP4)
        max_files: Maximum files to process
        scalar_bar_args: Scalar bar position/size arguments
        mesh_kwargs: Additional kwargs for add_mesh
        cmap: Colormap name
        clim: Color scale limits (min, max)
        framerate: Movie framerate
    """
    surf_dir = Path(surface_dir)
    d_len = len(list(surf_dir.iterdir()))

    if max_files is None:
        max_files = d_len

    if scalar_bar_args is None:
        scalar_bar_args = {
            'position_x': 0.9,
            'position_y': 0.3,
            'vertical': True
        }

    if mesh_kwargs is None:
        mesh_kwargs = {
            'cmap': cmap,
            'scalar_bar_args': scalar_bar_args
        }
        if clim:
            mesh_kwargs['clim'] = clim

    plotter = pyvista.Plotter()
    if movie_name:
        plotter.open_movie(movie_name, framerate=framerate)

    for t, mesh in surface_file_gen(surf_dir, fname, max_files):
        time_str = generate_timestamp(t, DEFAULT_START_TIME)

        try:
            plotter.add_mesh(mesh, scalars=vname, **mesh_kwargs)
            plotter.view_xy()
            plotter.add_text(
                f"time: {time_str}",
                position="upper_edge",
                font_size=8,
                color='black'
            )

            if movie_name:
                plotter.write_frame()

            plotter.clear()
        except Exception as e:
            print(f"Skipping file at t={t}: {e}")
            continue

    if movie_name:
        plotter.close()


def animate_multiple_surfaces(
    surface_dir: str,
    configs: list,
    num_workers: int = 4
):
    """
    Generate multiple animations in parallel.

    Args:
        surface_dir: Path to surfaces directory
        configs: List of dicts with keys: fname, vname, movie_name, etc.
        num_workers: Number of parallel workers
    """
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        for i, config in enumerate(configs):
            executor.submit(
                animate_surface,
                surface_dir,
                config['fname'],
                config['vname'],
                config.get('movie_name'),
                config.get('max_files'),
                config.get('scalar_bar_args'),
                config.get('mesh_kwargs'),
                config.get('cmap', 'viridis'),
                config.get('clim'),
                config.get('framerate', 30)
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate VTK animations from OpenFOAM surface files"
    )
    parser.add_argument("--surface_dir",
                        default="postProcessing/surfaces/",
                        help="Path to surfaces directory")
    parser.add_argument("--fname", required=True,
                        help="Surface file name (e.g., two_meter_terrain.vtp)")
    parser.add_argument("--vname", required=True,
                        help="Scalar variable name to plot")
    parser.add_argument("--movie_name",
                        help="Output movie filename")
    parser.add_argument("--max_files", type=int)
    parser.add_argument("--cmap", default="viridis")
    parser.add_argument("--clim", nargs=2, type=float,
                        help="Color scale limits: min max")

    args = parser.parse_args()

    animate_surface(
        args.surface_dir,
        args.fname,
        args.vname,
        args.movie_name,
        args.max_files,
        cmap=args.cmap,
        clim=tuple(args.clim) if args.clim else None
    )