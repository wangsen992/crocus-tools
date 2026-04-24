"""
LAS file preprocessing - transform coordinates and separate by classification.

Supports both single file and parallel processing.
"""

import laspy
import numpy as np
from pyproj import Transformer, CRS
import geojson
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import argparse
from typing import Optional


LAS_CLASSIFICATION = {
    "ground": [2, 11],
    "building": [6],
    "vegetation": [3, 4, 5],
    "water": [9],
}


def load_projection(proj_fname: str) -> CRS:
    """Load projection from file."""
    with open(proj_fname, "r") as f:
        proj_str = f.read()
    return CRS.from_proj4(proj_str)


def load_influence_region(geojson_path: str) -> tuple:
    """Load influence region and return bounding box."""
    with open(geojson_path, 'r') as f:
        gs = geojson.load(f)

    coords = np.array(gs["features"][0]["geometry"]["coordinates"]).squeeze()
    x1, y1 = coords.max(axis=0)
    x0, y0 = coords.min(axis=0)
    return x0, y0, x1, y1


def transform_las(
    las_path: str,
    target_crs: CRS,
    bounding_box: Optional[tuple] = None,
    z_scale: float = 0.3048
) -> laspy.LasData:
    """
    Transform LAS file to target coordinate system.

    Args:
        las_path: Path to input LAS file
        target_crs: Target projection (pyproj CRS)
        bounding_box: Optional (x0, y0, x1, y1) to subset data
        z_scale: Scale factor for z values (default 0.3048 feet to meters)

    Returns:
        Transformed LasData object
    """
    las = laspy.read(str(las_path))
    source_crs = las.header.parse_crs()

    proj = Transformer.from_crs(source_crs, target_crs)

    x, y, z = proj.transform(las.x, las.y, las.z)
    z = z * z_scale

    if bounding_box:
        x0, y0, x1, y1 = bounding_box
        cond = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)
        x, y, z = x[cond], y[cond], z[cond]

    new_file = laspy.create(
        point_format=las.point_format,
        file_version=las.header.version
    )
    new_file.x = x
    new_file.y = y
    new_file.z = z
    new_file.classification = las.classification
    new_file.scan_angle = las.scan_angle

    return new_file


def separate_by_classification(
    las_data: laspy.LasData,
    classes: dict = LAS_CLASSIFICATION
) -> dict:
    """
    Separate LAS data by classification codes.

    Args:
        las_data: Input LasData object
        classes: Dict mapping name to classification codes

    Returns:
        Dict mapping name to filtered LasData objects
    """
    result = {}
    for name, codes in classes.items():
        mask = np.array([c in codes for c in las_data.classification])
        filtered = laspy.create(
            point_format=las_data.point_format,
            file_version=las_data.header.version
        )
        filtered.points = las_data.points[mask]
        result[name] = filtered
    return result


def process_las_file(
    las_path: Path,
    proj_fname: str,
    subset_geojson: str,
    target_dir: Path
) -> dict:
    """
    Process a single LAS file - transform and separate by classification.

    Args:
        las_path: Path to input LAS file
        proj_fname: Path to projection file
        subset_geojson: Path to influence region GeoJSON
        target_dir: Output directory

    Returns:
        Dict with paths to output files
    """
    print(f"Processing {las_path.name}")

    target_crs = load_projection(proj_fname)
    x0, y0, x1, y1 = load_influence_region(subset_geojson)

    las_transformed = transform_las(las_path, target_crs, (x0, y0, x1, y1))

    separated = separate_by_classification(las_transformed)

    output_paths = {}
    for name, las_data in separated.items():
        if len(las_data.points) > 0:
            output_path = target_dir / f"{las_path.stem}_{name}.las"
            las_data.write(str(output_path))
            output_paths[name] = str(output_path)

    return output_paths


def merge_las_files(
    source_dir: Path | str,
    target_dir: Path | str,
    categories: list[str] = None,
    sample_fraction: float = 1.0,
) -> dict[str, Path]:
    """Merge and optionally subsample LAS files by category.

    Args:
        source_dir: Directory containing categorized LAS subdirs
                    (ground_las, building_las, vegetation_las, water_las)
        target_dir: Output directory for merged LAS files
        categories: List of category names to merge (default: all)
        sample_fraction: Fraction of points to keep (1.0 = keep all, 0.05 = 5%%)

    Returns:
        Dict mapping category name to merged LAS file path
    """
    if categories is None:
        categories = ["ground", "building", "vegetation", "water"]

    source_dir = Path(source_dir)
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    output_paths = {}
    for category in categories:
        category_dir = source_dir / f"{category}_las"
        if not category_dir.exists():
            continue

        las_files = list(category_dir.glob("*.las"))
        if not las_files:
            continue

        print(f"Merging {len(las_files)} {category} files...")

        all_points = []
        point_format = None
        file_version = None

        for las_file in las_files:
            las = laspy.read(str(las_file))
            all_points.append(las.points)
            if point_format is None:
                point_format = las.point_format
                file_version = las.header.version

        if not all_points:
            continue

        import numpy as np
        merged_points = np.concatenate(all_points)

        if sample_fraction < 1.0:
            n_keep = int(len(merged_points) * sample_fraction)
            indices = np.random.choice(len(merged_points), n_keep, replace=False)
            merged_points = merged_points[indices]

        merged_las = laspy.create(point_format=point_format, file_version=file_version)
        merged_las.points = merged_points

        output_path = target_dir / f"{category}.las"
        merged_las.write(str(output_path))
        output_paths[category] = output_path

        print(f"  -> {output_path} ({len(merged_points)} points)")

    return output_paths


def process_las_parallel(
    source_las_dir: str,
    proj_fname: str,
    subset_geojson: str,
    target_dir: str,
    num_workers: int = 4
) -> list:
    """
    Process multiple LAS files in parallel.

    Args:
        source_las_dir: Directory containing LAS files
        proj_fname: Path to projection file
        subset_geojson: Path to influence region GeoJSON
        target_dir: Output directory
        num_workers: Number of parallel workers

    Returns:
        List of result dicts
    """
    source_dir = Path(source_las_dir)
    target_path = Path(target_dir)

    for subdir in ["ground_las", "building_las", "vegetation_las", "water_las"]:
        (target_path / subdir).mkdir(parents=True, exist_ok=True)

    las_files = list(source_dir.glob("*.las"))

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        results = list(executor.map(
            lambda f: process_las_file(f, proj_fname, subset_geojson, target_path),
            las_files
        ))

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transform LAS files and separate by classification"
    )
    parser.add_argument("--proj_fname", "-p", default="proj4str.txt")
    parser.add_argument("--source_las", required=True,
                        help="Directory with LAS files or single file path")
    parser.add_argument("--subset_geojson", required=True,
                        help="Path to influence region GeoJSON")
    parser.add_argument("--target_dir", default="./results")
    parser.add_argument("--num_workers", type=int, default=4)

    args = parser.parse_args()

    source_path = Path(args.source_las)

    if source_path.is_dir():
        results = process_las_parallel(
            args.source_las,
            args.proj_fname,
            args.subset_geojson,
            args.target_dir,
            args.num_workers
        )
        print(f"Processed {len(results)} files")
    else:
        target_dir = Path(args.target_dir)
        for subdir in ["ground_las", "building_las", "vegetation_las", "water_las"]:
            (target_dir / subdir).mkdir(parents=True, exist_ok=True)

        result = process_las_file(source_path, args.proj_fname,
                                   args.subset_geojson, target_dir)
        print(f"Processed: {result}")