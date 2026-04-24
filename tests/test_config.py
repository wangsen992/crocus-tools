"""Tests for configuration generator."""

import tempfile
from pathlib import Path

from crocus.config import (
    generate_blockMeshDict,
    generate_controlDict,
    generate_decomposeParDict,
    load_yaml,
    render_template,
)


def test_load_yaml():
    """Test loading YAML configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "test.yaml"
        config_file.write_text("domain:\n  x: [0, 100]\n  y: [0, 100]\n")

        config = load_yaml(config_file)
        assert config["domain"]["x"] == [0, 100]


def test_render_template():
    """Test template rendering."""
    template = "value={{ value }}"
    result = render_template(template, {"value": 42})
    assert result == "value=42"

    template = "list={{ list }}"
    result = render_template(template, {"list": [1, 2, 3]})
    assert result == "list=(1 2 3)"

    template = "bool={{ flag }}"
    result = render_template(template, {"flag": True})
    assert result == "bool=yes"


def test_generate_blockMeshDict():
    """Test blockMeshDict generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        domain = {
            "x": [-1000, 1000],
            "y": [-1000, 1000],
            "z": [100, 600],
            "cells": [100, 100, 30],
        }
        output_path = Path(tmpdir) / "blockMeshDict"
        generate_blockMeshDict(domain, output_path)

        content = output_path.read_text()
        assert "1000 -1000 100" in content
        assert "100 100 30" in content


def test_generate_decomposeParDict():
    """Test decomposeParDict generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "domain": {"x": [-1000, 1000], "y": [-1000, 1000], "z": [100, 600], "cells": [100, 100, 30]},
            "decomposition": {"nDomains": 16, "simpleDecomN": [4, 4, 1], "method": "simple"},
        }
        output_path = Path(tmpdir) / "decomposeParDict"
        generate_decomposeParDict(config, output_path)

        content = output_path.read_text()
        assert "numberOfSubdomains 16" in content
        assert "simpleCoeffs" in content
        assert "(4 4 1)" in content