"""Subset building footprints from source CSV to target region."""

from pathlib import Path

import geopandas as gpd
import geojson
import numpy as np
from pyproj import CRS, Transformer


def subset_building_footprints(
    proj_fname: Path | str,
    source_bldfprt: Path | str,
    target_dir: Path | str = Path("."),
) -> Path:
    """Subset building footprints from source GeoJSON/CSV to influence region.

    Args:
        proj_fname: Path to PROJ string file defining target CRS
        source_bldfprt: Path to source building footprint file (GeoJSON or CSV)
        target_dir: Output directory

    Returns:
        Path to output buildings.geojson file
    """
    proj_fname = Path(proj_fname)
    source_bldfprt = Path(source_bldfprt)
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    with open(proj_fname) as f:
        proj_str = f.read()

    target_crs = CRS.from_proj4(proj_str)
    proj_st = Transformer.from_crs(target_crs, target_crs.geodetic_crs)

    influence_path = target_dir / "influenceRegion.geojson"
    with open(influence_path) as f:
        gs = geojson.load(f)

    coords = np.array(gs["features"][0]["geometry"]["coordinates"]).squeeze()
    x1, y1 = coords.max(axis=0)
    x0, y0 = coords.min(axis=0)

    lon0, lat0 = proj_st.transform(x0, y0)
    lon1, lat1 = proj_st.transform(x1, y1)

    gdf = gpd.read_file(source_bldfprt)
    gdf = gpd.GeoDataFrame(
        geometry=gpd.GeoSeries.from_wkt(gdf['the_geom'], crs='latlon'),
        data=gdf
    )
    gdf = gdf.set_crs("latlon")

    gdf_subset = gdf.cx[lon0:lon1, lat0:lat1]
    gdf_subset = gdf_subset.to_crs(target_crs)

    output_path = target_dir / "buildings.geojson"
    gdf_subset.to_file(output_path, driver="GeoJSON")

    return output_path


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="crocus footprints",
        description="Subset building footprints from source file to influence region",
    )
    parser.add_argument("--proj_fname", "-p", default="proj4str.txt")
    parser.add_argument("--source_bldfprt", required=True)
    parser.add_argument("--target_dir", default=".")

    args = parser.parse_args()

    output_path = subset_building_footprints(
        proj_fname=args.proj_fname,
        source_bldfprt=args.source_bldfprt,
        target_dir=args.target_dir,
    )
    print(f"Created: {output_path}")


if __name__ == "__main__":
    main()