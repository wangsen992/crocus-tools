"""
Canopy LAD (Leaf Area Density) processing from LiDAR data

Voxelizes vegetation point clouds and computes LAD using Beer-Lambert law.
"""

import numpy as np
import laspy
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from typing import Tuple, List


def voxelize(ar: np.ndarray, bottom: np.ndarray, vwidth: float) -> Tuple:
    """
    Voxelize point cloud into 3D grid.

    Args:
        ar: Point cloud array (N x 3) - vegetation points
        bottom: Ground points array (M x 3)
        vwidth: Voxel width in same units as points

    Returns:
        Tuple of (vx, vy, vz, vcnt, vbcnt)
    """
    domain_min = np.min([ar.min(axis=0), bottom.min(axis=0)], axis=0)
    ar_i = ((ar - domain_min) / vwidth).astype("int")
    bottom_i = ((bottom - domain_min) / vwidth).astype("int")
    domain_i_max = np.max([ar_i.max(axis=0), bottom_i.max(axis=0)], axis=0)

    xi_counter = np.unique(ar_i, axis=0, return_counts=True)
    xbi_counter = np.unique(bottom_i, axis=0, return_counts=True)

    vcnt = np.zeros(domain_i_max + 1)
    vbcnt = np.zeros(domain_i_max[:2] + 1)

    xi_tuple = xi_counter[0]
    xi_counts = xi_counter[1]
    for i in range(xi_counts.size):
        t = xi_tuple[i]
        vcnt[t[0] - 1, t[1] - 1, t[2] - 1] = xi_counts[i]

    xbi_tuple = xbi_counter[0]
    xbi_counts = xbi_counter[1]
    for i in range(xbi_counts.size):
        t = xbi_tuple[i]
        if t[0] >= 0 and t[1] >= 0:
            vbcnt[t[0] - 1, t[1] - 1] = xbi_counts[i]

    x, y, z = ar[:, 0], ar[:, 1], ar[:, 2]
    vx = np.arange(x.min(), x.max() + vwidth, vwidth)
    vy = np.arange(y.min(), y.max() + vwidth, vwidth)
    vz = np.arange(z.min(), z.max() + vwidth, vwidth)

    return vx, vy, vz, vcnt, vbcnt


def compute_lad(vcnt: np.ndarray, vbcnt: np.ndarray, vwidth: float,
                k: float = 0.5) -> np.ndarray:
    """
    Compute Leaf Area Density using Beer-Lambert theory.

    Args:
        vcnt: 3D voxel counts (vegetation points per voxel)
        vbcnt: 2D bottom counts (ground points per column)
        vwidth: Voxel width
        k: Beer-Lambert extinction coefficient (default 0.5)

    Returns:
        LAD array of same shape as vcnt
    """
    vcnt_cb = np.concatenate([vbcnt[..., np.newaxis], vcnt], axis=2)
    vcnt_cb_sum = vcnt_cb.cumsum(axis=2)
    vcnt_cb_sum[vcnt_cb_sum == 0] = 1

    vcnt_cb_sum_tmp = np.log(vcnt_cb_sum[:, :, 1:] / vcnt_cb_sum[:, :, :-1])
    lad = vcnt_cb_sum_tmp / (k * vwidth)

    return lad


def to_openfoam_list(name: str, list_data: List[str]) -> str:
    """Format list data as OpenFOAM nonuniform list."""
    return f"{name} nonuniform {len(list_data)}\n" + \
           "(\n\t" + "\n\t".join(list_data) + "\n);"


def write_lad_openfoam(points_list: List[str], lad_list: List[str],
                       output_path: str = "constant/urban/point_data/lad"):
    """Write LAD data in OpenFOAM dictionary format."""
    header = """
    FoamFile
    {
        version 2.0;
        format  ascii;
        class   dictionary;
        object  lad;
    }
    // * * * * * * * * * * * * * * * * * * * * * * * * * * * *
    """

    points_entry = to_openfoam_list("points", points_list)
    lad_entry = to_openfoam_list("lad", lad_list)
    dimension_entry = "dimension  [0 -1 0 0 0];\n"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', buffering=8192) as f:
        f.write(header)
        f.write(dimension_entry)
        f.write(points_entry)
        f.write(lad_entry)

    print(f"LAD written to {output_path}")


def process_vegetation_file(veg_path: Path, gnd_path: Path,
                            spacing: float = 0.5) -> Tuple[List[str], List[str]]:
    """
    Process a single vegetation LAS file with corresponding ground file.

    Args:
        veg_path: Path to vegetation LAS file
        gnd_path: Path to ground LAS file
        spacing: Voxel spacing in meters

    Returns:
        Tuple of (points_list, lad_list)
    """
    veg_las = laspy.read(str(veg_path))

    if len(veg_las) < 10:
        print(f"No veg points {veg_path}")
        return [], []

    ground_las = laspy.read(str(gnd_path))

    print(f"Processing {veg_path}")

    veg_points = veg_las.xyz
    terrain_points = ground_las.xyz

    x, y, z, vcnt, vbcnt = voxelize(veg_points, terrain_points, spacing)

    lad = compute_lad(vcnt, vbcnt, spacing)

    points_list = []
    lad_list = []

    for i in range(x.size - 1):
        for j in range(y.size - 1):
            for k in range(z.size - 1):
                if lad[i, j, k] > 0:
                    points_list.append(f"({x[i]:6.2f} {y[j]:6.2f} {z[k]:6.2f})")
                    lad_list.append(f"{lad[i,j,k]:4.2f}")

    return points_list, lad_list


def voxelize_las(veg_dir: str, gnd_dir: str, output: str = None,
                 num_workers: int = 4, spacing: float = 0.5):
    """
    Convert LiDAR vegetation points to OpenFOAM LAD format.

    Args:
        veg_dir: Directory containing vegetation LAS files
        gnd_dir: Directory containing ground LAS files
        output: Output path for LAD file (default: constant/urban/point_data/lad)
        num_workers: Number of parallel workers
        spacing: Voxel spacing in meters
    """
    veg_dir = Path(veg_dir)
    gnd_dir = Path(gnd_dir)

    if output is None:
        output = "constant/urban/point_data/lad"

    points_list = []
    lad_list = []

    veg_files = sorted(veg_dir.glob("*_veg.las"))

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        for veg_file in veg_files:
            prefix = veg_file.stem.split("_veg")[0]
            gnd_file = gnd_dir / f"{prefix}_ground.las"

            if not gnd_file.exists():
                print(f"Warning: No ground file for {veg_file}")
                continue

            for pl, ll in [executor.map(
                lambda f: process_vegetation_file(f, gnd_file, spacing),
                [veg_file]
            )]:
                points_list.extend(pl)
                lad_list.extend(ll)

    write_lad_openfoam(points_list, lad_list, output)

    print(f"Processed {len(points_list)} LAD points")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert LiDAR vegetation to OpenFOAM LAD"
    )
    parser.add_argument("--veg_dir", default="ppcfd_results/vegetation_las",
                        help="Directory with vegetation LAS files")
    parser.add_argument("--gnd_dir", default="ppcfd_results/ground_las",
                        help="Directory with ground LAS files")
    parser.add_argument("--output", default="constant/urban/point_data/lad",
                        help="Output path")
    parser.add_argument("--num_workers", type=int, default=4)
    parser.add_argument("--spacing", type=float, default=0.5,
                        help="Voxel spacing in meters")

    args = parser.parse_args()

    voxelize_las(args.veg_dir, args.gnd_dir, args.output,
                 args.num_workers, args.spacing)