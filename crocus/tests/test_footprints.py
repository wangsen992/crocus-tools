"""Tests for footprints module."""

import tempfile
from pathlib import Path

import pytest

from crocus.footprints import subset_building_footprints


@pytest.fixture
def influence_region_file(tmp_path):
    """Create a test influence region GeoJSON."""
    import geojson

    coords = [[(-87.65, 41.86), (-87.55, 41.86), (-87.55, 41.90), (-87.65, 41.90), (-87.65, 41.86)]]
    feature = {
        "type": "Feature",
        "geometry": {"type": "MultiPolygon", "coordinates": coords},
        "properties": {},
    }
    fc = {"type": "FeatureCollection", "features": [feature], "name": "influenceRegion"}

    path = tmp_path / "influenceRegion.geojson"
    with open(path, "w") as f:
        geojson.dump(fc, f)
    return path


def test_subset_building_footprints(tmp_path, influence_region_file):
    """Test building footprint subsetting."""
    proj_file = tmp_path / "proj4str.txt"
    proj_file.write_text("+proj=lcc +lat_0=41.9 +lon_0=-87.6 +lat_1=33 +lat_2=45 +ellps=GRS80")

    source_file = tmp_path / "buildings.csv"
    source_file.write_text("the_geom\n")

    target_dir = tmp_path

    output_path = subset_building_footprints(
        proj_fname=proj_file,
        source_bldfprt=source_file,
        target_dir=target_dir,
    )

    assert output_path.exists()
    assert output_path.name == "buildings.geojson"