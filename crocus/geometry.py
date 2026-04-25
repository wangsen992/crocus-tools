"""
Building and terrain geometry processing tools.

Creates boundary GeoJSON files for city4cfd and CFD domain.
"""

from pyproj import Transformer, CRS
import geojson
from geojson import Feature, MultiPolygon, FeatureCollection
from pathlib import Path
from typing import Optional
import argparse


def create_boundary_feature(x0: float, y0: float, buffer: float,
                             name: str) -> FeatureCollection:
    """
    Create a rectangular boundary feature.

    Args:
        x0: Center X coordinate
        y0: Center Y coordinate
        buffer: Half-width of rectangle
        name: Feature name

    Returns:
        FeatureCollection with single polygon
    """
    mp = MultiPolygon([
        ([(x0 - buffer, y0 - buffer),
          (x0 + buffer, y0 - buffer),
          (x0 + buffer, y0 + buffer),
          (x0 - buffer, y0 + buffer)])
    ])
    mp['coordinates'] = [mp['coordinates']]

    feature = Feature(geometry=mp)
    feature_collection = FeatureCollection([feature])
    feature_collection['name'] = name

    return feature_collection


def create_bounds(lon0: float, lat0: float,
                  building_buffer: int = 200,
                  domain_buffer: int = 300,
                  proj_fname: str = "proj4str.txt",
                  target_dir: str = "./results") -> dict:
    """
    Create boundary GeoJSON files for city4cfd processing.

    Args:
        lon0: Longitude of domain center
        lat0: Latitude of domain center
        building_buffer: Buffer around center for city4cfd influence region (meters)
        domain_buffer: Buffer around center for CFD domain (meters)
        proj_fname: Projection file path
        target_dir: Output directory

    Returns:
        Dictionary with paths to created files
    """
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    with open(proj_fname, "r") as f:
        proj_str = f.read()

    proj_crs = CRS.from_proj4(proj_str)
    proj_st = Transformer.from_crs(proj_crs, proj_crs.geodetic_crs)

    x0, y0 = proj_st.transform(lon0, lat0, direction="INVERSE")
    print(f"Center coordinates: x0={x0:.2f}, y0={y0:.2f}")

    c4c_bnd = create_boundary_feature(x0, y0, building_buffer, "influenceRegion")
    domain_bnd = create_boundary_feature(x0, y0, domain_buffer, "domainBnd")

    influence_path = target_dir / "influenceRegion.geojson"
    domain_path = target_dir / "domainBnd.geojson"

    with open(influence_path, "w") as f:
        f.write(geojson.dumps(c4c_bnd))

    with open(domain_path, "w") as f:
        f.write(geojson.dumps(domain_bnd))

    return {
        "influenceRegion": str(influence_path),
        "domainBnd": str(domain_path)
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create boundaries for city4cfd and CFD domain"
    )
    parser.add_argument("--proj_fname", "-p", default="proj4str.txt")
    parser.add_argument("--lon0", type=float, required=True)
    parser.add_argument("--lat0", type=float, required=True)
    parser.add_argument("--building_buffer", type=int, default=200)
    parser.add_argument("--domain_buffer", type=int, default=300)
    parser.add_argument("--target_dir", default="./results")

    args = parser.parse_args()

    result = create_bounds(
        args.lon0, args.lat0,
        args.building_buffer, args.domain_buffer,
        args.proj_fname, args.target_dir
    )
    print(f"Created: {result}")