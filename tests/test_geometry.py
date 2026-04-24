"""
Tests for geometry module.
"""

import pytest
from pathlib import Path
import tempfile
import os
from crocus.geometry import create_bounds, create_boundary_feature


class TestGeometry:
    """Test geometry processing functions."""

    def test_create_boundary_feature(self):
        """Test boundary feature creation."""
        feature = create_boundary_feature(0, 0, 100, "test_region")

        assert feature is not None
        assert feature['name'] == "test_region"
        assert len(feature['features']) == 1

        coords = feature['features'][0]['geometry']['coordinates']
        assert len(coords) == 1

    def test_create_bounds_output_files(self):
        """Test create_bounds creates output files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            proj_file = Path(tmpdir) / "proj4str.txt"
            target_dir = Path(tmpdir) / "output"

            with open(proj_file, 'w') as f:
                f.write("+proj=lcc +lat_0=41.8 +lon_0=-87.6 +lat_1=33 +lat_2=45 +ellps=GRS80")

            result = create_bounds(
                lon0=-87.6463732,
                lat0=41.8692893,
                building_buffer=200,
                domain_buffer=300,
                proj_fname=str(proj_file),
                target_dir=str(target_dir)
            )

            assert Path(result['influenceRegion']).exists()
            assert Path(result['domainBnd']).exists()


if __name__ == "__main__":
    pytest.main([__file__])