"""
Tests for CROCUS-UES3 Python tools
"""

import pytest
import numpy as np
from crocus.canopy import voxelize, compute_lad


class TestCanopy:
    """Test canopy processing functions."""

    def test_voxelize_basic(self):
        """Test basic voxelization."""
        ar = np.array([[0, 0, 1], [0.1, 0.1, 2], [0.2, 0.2, 1.5]])
        bottom = np.array([[0, 0, 0], [0.5, 0.5, 0]])

        vx, vy, vz, vcnt, vbcnt = voxelize(ar, bottom, 0.5)

        assert len(vx) > 0
        assert len(vy) > 0
        assert len(vz) > 0
        assert vcnt.shape[0] > 0

    def test_compute_lad(self):
        """Test LAD computation."""
        vcnt = np.zeros((3, 3, 3))
        vcnt[1, 1, 0] = 10
        vcnt[1, 1, 1] = 20

        vbcnt = np.zeros((3, 3))
        vbcnt[1, 1] = 5

        lad = compute_lad(vcnt, vbcnt, 0.5)

        assert lad.shape == vcnt.shape
        assert np.all(lad >= 0)


if __name__ == "__main__":
    pytest.main([__file__])