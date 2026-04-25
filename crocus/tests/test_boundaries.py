"""Tests for boundaries module."""

import tempfile
from pathlib import Path

import pytest

from crocus.boundaries import create_bnd, create_boundaries


def test_create_bnd():
    """Test creating a single boundary."""
    result = create_bnd(0, 0, 100, "testRegion")

    assert result["name"] == "testRegion"
    assert len(result["features"]) == 1
    assert result["features"][0]["geometry"]["type"] == "MultiPolygon"


def test_create_boundaries():
    """Test creating boundary files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        proj_file = Path(tmpdir) / "proj4str.txt"
        proj_file.write_text("+proj=lcc +lat_0=41.9 +lon_0=-87.6 +lat_1=33 +lat_2=45 +ellps=GRS80")

        influence_path, domain_path = create_boundaries(
            proj_fname=proj_file,
            lon0=-87.6,
            lat0=41.9,
            building_buffer=200,
            domain_buffer=300,
            target_dir=tmpdir,
        )

        assert influence_path.exists()
        assert domain_path.exists()
        assert influence_path.name == "influenceRegion.geojson"
        assert domain_path.name == "domainBnd.geojson"