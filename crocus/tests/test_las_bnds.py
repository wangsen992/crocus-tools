"""Tests for las_bnds module."""

import tempfile
from pathlib import Path

from crocus.las_bnds import get_las_bounding_box


def test_get_las_bounding_box():
    """Test LAS bounding box calculation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_file = Path(tmpdir) / "proj4str.txt"
        proj_file.write_text("+proj=lcc +lat_0=41.9 +lon_0=-87.6 +lat_1=33 +lat_2=45 +ellps=GRS80")

        las_proj_file = Path(tmpdir) / "las_proj.txt"
        las_proj_file.write_text('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]')

        subset_geojson = Path(tmpdir) / "subset.geojson"
        import geojson
        coords = [[(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]]
        feature = {
            "type": "Feature",
            "geometry": {"type": "MultiPolygon", "coordinates": coords},
            "properties": {},
        }
        fc = {"type": "FeatureCollection", "features": [feature]}
        with open(subset_geojson, "w") as f:
            geojson.dump(fc, f)

        result = get_las_bounding_box(
            proj_fname=proj_file,
            subset_geojson=subset_geojson,
            las_proj_fname=las_proj_file,
        )

        assert isinstance(result, str)
        parts = result.split()
        assert len(parts) == 4
        assert all(p.isdigit() or p.startswith("-") for p in parts)