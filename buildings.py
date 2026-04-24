"""
Building footprint subsetting and projection transformation.

Clips building footprints to a given region and transforms coordinates.
"""

import geojson
import geopandas as gpd
import numpy as np
from pyproj import CRS, Transformer
from pathlib import Path
import argparse


def subset_buildings(
    source_bldfprt: str,
    influence_region: str,
    proj_fname: str,
    target_dir: str = "./results"
) -> str:
    """
    Subset building footprints to influence region and transform to target CRS.

    Args:
        source_bldfprt: Path to source building footprints (CSV or GeoJSON)
        influence_region: Path to influence region GeoJSON
        proj_fname: Path to target projection file
        target_dir: Output directory

    Returns:
        Path to output GeoJSON file
    """
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    with open(proj_fname, "r") as f:
        proj_str = f.read()

    target_crs = CRS.from_proj4(proj_str)
    proj_st = Transformer.from_crs(target_crs, target_crs.geodetic_crs)

    with open(influence_region, 'r') as f:
        gs = geojson.load(f)

    coords = np.array(gs["features"][0]["geometry"]["coordinates"]).squeeze()
    x1, y1 = coords.max(axis=0)
    x0, y0 = coords.min(axis=0)
    lon0, lat0 = proj_st.transform(x0, y0)
    lon1, lat1 = proj_st.transform(x1, y1)

    if source_bldfprt.endswith('.csv'):
        gdf = gpd.read_file(source_bldfprt)
        gdf = gpd.GeoDataFrame(
            geometry=gpd.GeoSeries.from_wkt(gdf['the_geom'], crs='latlon'),
            data=gdf
        )
        gdf = gdf.set_crs("latlon")
    else:
        gdf = gpd.read_file(source_bldfprt)

    gdf_subset = gdf.cx[lon0:lon1, lat0:lat1]
    gdf_subset = gdf_subset.to_crs(target_crs)

    output_path = target_dir / "buildings.geojson"
    gdf_subset.to_file(str(output_path), driver="GeoJSON")

    print(f"Subset {len(gdf_subset)} buildings, saved to {output_path}")
    return str(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Subset building footprints to influence region"
    )
    parser.add_argument("--proj_fname", "-p", default="proj4str.txt")
    parser.add_argument("--source_bldfprt", required=True)
    parser.add_argument("--influence_region",
                        help="Path to influence region GeoJSON "
                             "(default: {target_dir}/influenceRegion.geojson)")
    parser.add_argument("--target_dir", default="./results")

    args = parser.parse_args()

    if args.influence_region is None:
        args.influence_region = f"{args.target_dir}/influenceRegion.geojson"

    result = subset_buildings(
        args.source_bldfprt,
        args.influence_region,
        args.proj_fname,
        args.target_dir
    )
    print(f"Output: {result}")