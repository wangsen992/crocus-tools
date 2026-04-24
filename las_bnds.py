"""Get bounding box coordinates for LAS subsetting."""

from pathlib import Path

import geojson
import numpy as np
from pyproj import CRS, Transformer


def get_las_bounding_box(
    proj_fname: Path | str,
    subset_geojson: Path | str,
    las_proj_fname: Path | str,
) -> str:
    """Get bounding box string for LAStools -inside parameter.

    Args:
        proj_fname: Path to target PROJ string file
        subset_geojson: Path to subset region GeoJSON file
        las_proj_fname: Path to LAS file CRS (WKT format)

    Returns:
        String "x0 y0 x1 y1" for LAStools -inside parameter
    """
    proj_fname = Path(proj_fname)
    subset_geojson = Path(subset_geojson)
    las_proj_fname = Path(las_proj_fname)

    with open(proj_fname) as f:
        proj_str = f.read()
    target_crs = CRS.from_proj4(proj_str)

    with open(las_proj_fname) as f:
        las_crs_wkt = f.read()
    source_crs = CRS.from_wkt(las_crs_wkt)

    proj = Transformer.from_crs(source_crs, target_crs)

    with open(subset_geojson) as f:
        gs = geojson.load(f)

    coords = np.array(gs["features"][0]["geometry"]["coordinates"]).squeeze()
    x1, y1 = coords.max(axis=0)
    x0, y0 = coords.min(axis=0)

    (lasx0, lasx1), (lasy0, lasy1) = proj.transform(
        (x0, x1), (y0, y1), direction="INVERSE"
    )

    return f"{int(lasx0)} {int(lasy0)} {int(lasx1)} {int(lasy1)}"


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="crocus las-bnds",
        description="Get bounding box for LAS subsetting",
    )
    parser.add_argument("--proj_fname", "-p", default="proj4str.txt")
    parser.add_argument("--subset_geojson", required=True)
    parser.add_argument("--las_proj_fname", default="las_proj.txt")

    args = parser.parse_args()

    result = get_las_bounding_box(
        proj_fname=args.proj_fname,
        subset_geojson=args.subset_geojson,
        las_proj_fname=args.las_proj_fname,
    )
    print(result)


if __name__ == "__main__":
    main()