"""
CROCUS-UES3: Urban CFD Simulation Tools

A Python package for managing urban CFD simulations including:
- LiDAR to canopy LAD conversion
- Building/terrain geometry processing
- LAS file preprocessing
- ERA5 forcing generation
- Visualization tools
"""

__version__ = "0.1.0"
__author__ = "Sen Wang"

from .canopy import voxelize_las, compute_lad, process_vegetation_file
from .geometry import create_bounds
from .las_prep import process_las_file, process_las_parallel
from .buildings import subset_buildings
from .visualization import animate_surface, animate_multiple_surfaces

__all__ = [
    "voxelize_las",
    "compute_lad",
    "process_vegetation_file",
    "create_bounds",
    "process_las_file",
    "process_las_parallel",
    "subset_buildings",
    "animate_surface",
    "animate_multiple_surfaces",
]