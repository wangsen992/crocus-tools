"""Create boundary GeoJSON files for city4cfd and CFD domain."""

from pathlib import Path
from typing import Optional

import geojson
from geojson import Feature, FeatureCollection, MultiPolygon
from pyproj import CRS, Transformer


def create_bnd(x0: float, y0: float, buffer: float, name: str) -> FeatureCollection:
    """Create a square boundary feature collection.

    Args:
        x0: Center X coordinate (in projected CRS)
        y0: Center Y coordinate (in projected CRS)
        buffer: Half-width of the square
        name: Name for the feature collection

    Returns:
        GeoJSON FeatureCollection with a single square polygon
    """
    mp = MultiPolygon([
        ([(x0-buffer, y0-buffer), (x0+buffer, y0-buffer),
          (x0+buffer, y0+buffer), (x0-buffer, y0+buffer), (x0-buffer, y0-buffer)])
    ])
    mp['coordinates'] = [mp['coordinates']]

    feature = Feature(geometry=mp)
    feature_collection = FeatureCollection([feature])
    feature_collection['name'] = name
    return feature_collection


def create_boundaries(
    proj_fname: Path | str,
    lon0: float,
    lat0: float,
    building_buffer: float = 200,
    domain_buffer: float = 300,
    target_dir: Path | str = Path("."),
) -> tuple[Path, Path]:
    """Create influence region and domain boundary GeoJSON files.

    Args:
        proj_fname: Path to PROJ string file (e.g., proj4str.txt)
        lon0: Longitude of center point
        lat0: Latitude of center point
        building_buffer: Buffer size for city4cfd influence region (meters)
        domain_buffer: Buffer size for CFD domain boundary (meters)
        target_dir: Output directory for GeoJSON files

    Returns:
        Tuple of (influence_region_path, domain_boundary_path)
    """
    proj_fname = Path(proj_fname)
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    with open(proj_fname) as f:
        proj_str = f.read()

    proj_crs = CRS.from_proj4(proj_str)
    proj_st = Transformer.from_crs(proj_crs, proj_crs.geodetic_crs)

    x0, y0 = proj_st.transform(lon0, lat0, direction="INVERSE")

    influence_bnd = create_bnd(x0, y0, building_buffer, "influenceRegion")
    domain_bnd = create_bnd(x0, y0, domain_buffer, "domainBnd")

    influence_path = target_dir / "influenceRegion.geojson"
    domain_path = target_dir / "domainBnd.geojson"

    with open(influence_path, "w") as f:
        f.write(geojson.dumps(influence_bnd))
    with open(domain_path, "w") as f:
        f.write(geojson.dumps(domain_bnd))

    return influence_path, domain_path


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="crocus boundaries",
        description="Create boundary GeoJSON files for city4cfd and CFD domain",
    )
    parser.add_argument("--proj_fname", "-p", default="proj4str.txt")
    parser.add_argument("--lon0", type=float, required=True)
    parser.add_argument("--lat0", type=float, required=True)
    parser.add_argument("--building_buffer", type=int, default=200)
    parser.add_argument("--domain_buffer", type=int, default=300)
    parser.add_argument("--target_dir", default=".")

    args = parser.parse_args()

    influence_path, domain_path = create_boundaries(
        proj_fname=args.proj_fname,
        lon0=args.lon0,
        lat0=args.lat0,
        building_buffer=args.building_buffer,
        domain_buffer=args.domain_buffer,
        target_dir=args.target_dir,
    )
    print(f"Created: {influence_path}, {domain_path}")


if __name__ == "__main__":
    main()