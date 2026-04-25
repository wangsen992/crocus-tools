"""city4cfd wrapper for CROCUS-UES3 urban CFD meshing."""

import json
import shutil
from pathlib import Path
from typing import Optional

import yaml

from crocus.boundaries import create_boundaries
from crocus.footprints import subset_building_footprints
from crocus.las_bnds import get_las_bounding_box
from crocus.las_prep import process_las_parallel, merge_las_files


CITY4CFD_CONFIG_TEMPLATE = {
    "point_clouds": {
        "ground": "../ppcfd_results/ground.las",
        "buildings": "../ppcfd_results/building.las",
    },
    "polygons": [
        {
            "type": "Building",
            "path": "../ppcfd_results/buildings_simplified.geojson",
            "unique_id": "BLDG_ID",
        }
    ],
    "reconstruction_regions": [
        {
            "influence_region": "../ppcfd_results/influenceRegion.geojson",
            "lod": "1.2",
            "complexity_factor": 0.3,
        }
    ],
    "point_of_interest": [0, 0],
    "domain_bnd": "../ppcfd_results/domainBnd.geojson",
    "top_height": 500,
    "bnd_type_bpg": "Rectangle",
    "bpg_blockage_ratio": False,
    "flow_direction": [1, 0],
    "buffer_region": -15,
    "reconstruct_boundaries": True,
    "terrain_thinning": 80,
    "smooth_terrain": {
        "iterations": 1,
        "max_pts": 1000000000,
    },
    "building_percentile": 90,
    "min_height": 5,
    "min_area": 70,
    "edge_max_len": 5,
    "output_file_name": "Mesh",
    "output_format": "stl",
    "output_separately": True,
    "output_log": True,
    "log_file": "logFile.log",
}


class City4CFDRunner:
    """Wrapper for city4cfd mesh generation workflow.

    Handles pre-processing (boundaries, footprints, LAS prep) and
    execution of the city4cfd binary.
    """

    @staticmethod
    def _find_city4cfd_bin() -> Path | None:
        """Search for city4cfd binary in common locations.

        Returns:
            Path to city4cfd binary if found, None otherwise
        """
        import os
        import subprocess

        search_paths = [
            # Conda env (primary build location)
            Path(os.environ.get("CONDA_PREFIX", "")) / "bin" / "city4cfd",
            # Home directory local installs
            Path.home() / ".local" / "bin" / "city4cfd",
            Path.home() / ".local" / "city4cfd" / "bin" / "city4cfd",
            # Project source build
            Path(__file__).parent.parent.parent / "src" / "city4cfd" / "build" / "city4cfd",
            # Old container location (for backward compatibility)
            Path("/app/City4CFD/build/city4cfd"),
        ]

        for p in search_paths:
            if p.exists() and p.is_file():
                # Verify it's executable
                if os.access(p, os.X_OK):
                    return p
            # Also check if it's in PATH via 'which'
            try:
                result = subprocess.run(
                    ["which", "city4cfd"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return Path(result.stdout.strip())
            except Exception:
                pass

        return None

    def __init__(
        self,
        case_dir: Path | str,
        city4cfd_bin: Path | str | None = None,
        polyprep_bin: Path | str | None = None,
        las_tools_dir: Path | str | None = None,
    ):
        """Initialize city4cfd runner.

        Args:
            case_dir: Path to simulation case directory
            city4cfd_bin: Path to city4cfd binary (auto-detected if None)
            polyprep_bin: Path to polyprep.py script (auto-detected if None)
            las_tools_dir: Path to LAStools bin directory

        Raises:
            FileNotFoundError: If city4cfd binary not found
        """
        self.case_dir = Path(case_dir)

        # Auto-detect city4cfd binary
        if city4cfd_bin is None:
            detected_bin = self._find_city4cfd_bin()
            if detected_bin is None:
                raise FileNotFoundError(
                    "city4cfd binary not found.\n"
                    "Please build city4cfd first:\n"
                    "  ./scripts/build_city4cfd.sh\n"
                    "Then activate the environment:\n"
                    "  conda activate city4cfd-env"
                )
            city4cfd_bin = detected_bin

        self.city4cfd_bin = Path(city4cfd_bin)

        # Auto-detect polyprep (usually next to city4cfd or in src/tools)
        if polyprep_bin is None:
            possible_polyprep = [
                self.city4cfd_bin.parent / "city4cfd_pcprep",
                Path(__file__).parent.parent.parent / "src" / "city4cfd" / "tools" / "polyprep" / "polyprep.py",
            ]
            for p in possible_polyprep:
                if p.exists():
                    polyprep_bin = p
                    break

        self.polyprep_bin = Path(polyprep_bin) if polyprep_bin else None
        self.las_tools_dir = Path(las_tools_dir) if las_tools_dir else None

        self.ppcfd_results = self.case_dir / "ppcfd_results"
        self.city4cfd_dir = self.case_dir / "city4cfd"
        self.tri_surface = self.case_dir / "constant" / "triSurface"

    def generate_config(
        self,
        output_path: Path | str | None = None,
        top_height: float = 500,
        building_buffer: float = 200,
        domain_buffer: float = 300,
        **kwargs,
    ) -> Path:
        """Generate city4cfd config_bpg.json from template.

        Args:
            output_path: Output path for config file
            top_height: Maximum building height
            building_buffer: Buffer around buildings for influence region
            domain_buffer: Buffer for domain boundary
            **kwargs: Additional config overrides

        Returns:
            Path to generated config file
        """
        if output_path is None:
            output_path = self.city4cfd_dir / "config_bpg.json"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        config = CITY4CFD_CONFIG_TEMPLATE.copy()
        config["top_height"] = top_height
        config["reconstruction_regions"][0]["influence_region"] = (
            "../ppcfd_results/influenceRegion.geojson"
        )

        for key, value in kwargs.items():
            if key in config:
                config[key] = value

        with open(output_path, "w") as f:
            json.dump(config, f, indent=2)

        return output_path

    def run_prep(
        self,
        proj_fname: Path | str,
        lon0: float,
        lat0: float,
        building_footprint_source: Path | str,
        las_source_dir: Path | str,
        las_proj_fname: Path | str,
        building_buffer: float = 600,
        domain_buffer: float = 1500,
        polyprep_buffer: float = 1.0,
        polyprep_simplification_tol: float = 0.1,
        polyprep_remove_holes: bool = True,
        num_workers: int = 4,
        subsample_fraction: float = 0.05,
    ) -> None:
        """Run pre-processing steps for city4cfd.

        Args:
            proj_fname: Path to PROJ string file
            lon0: Longitude of center point
            lat0: Latitude of center point
            building_footprint_source: Path to source building footprints CSV
            las_source_dir: Directory containing source LAS tiles
            las_proj_fname: Path to LAS file CRS (WKT format)
            building_buffer: Buffer size for influence region (meters)
            domain_buffer: Buffer size for domain boundary (meters)
            polyprep_buffer: Buffer size for polyprep simplification
            polyprep_simplification_tol: Simplification tolerance for polyprep
            polyprep_remove_holes: Whether to remove holes in polyprep
            num_workers: Number of parallel workers for LAS processing
            subsample_fraction: Fraction of points to subsample (0.05 = 5%)
        """
        self.ppcfd_results.mkdir(parents=True, exist_ok=True)

        print("[city4cfd] Creating boundary GeoJSONs...")
        create_boundaries(
            proj_fname=proj_fname,
            lon0=lon0,
            lat0=lat0,
            building_buffer=building_buffer,
            domain_buffer=domain_buffer,
            target_dir=self.ppcfd_results,
        )

        print("[city4cfd] Subsetting building footprints...")
        subset_building_footprints(
            proj_fname=proj_fname,
            source_bldfprt=building_footprint_source,
            target_dir=self.ppcfd_results,
        )

        print("[city4cfd] Simplifying buildings with polyprep...")
        buildings_path = self.ppcfd_results / "buildings.geojson"
        buildings_simplified_path = self.ppcfd_results / "buildings_simplified.geojson"
        polyprep_cmd = [
            "python",
            str(self.polyprep_bin),
            str(buildings_path),
            str(buildings_simplified_path),
            str(polyprep_buffer),
            "--simplification_tol",
            str(polyprep_simplification_tol),
        ]
        if polyprep_remove_holes:
            polyprep_cmd.append("--remove_holes")
        import subprocess
        subprocess.run(polyprep_cmd, check=True)

        print("[city4cfd] Getting LAS bounding box...")
        xy_region = get_las_bounding_box(
            proj_fname=proj_fname,
            subset_geojson=self.ppcfd_results / "influenceRegion.geojson",
            las_proj_fname=las_proj_fname,
        )
        print(f"[city4cfd] LAS bounding box: {xy_region}")

        print("[city4cfd] Processing LAS files in parallel...")
        subset_las_dir = self.ppcfd_results / "subset_las"
        subset_las_dir.mkdir(exist_ok=True)

        import subprocess
        las_files = list(Path(las_source_dir).glob("*.las"))
        for las_file in las_files:
            output_name = f"subset_{las_file.name}"
            output_path = subset_las_dir / output_name
            las2las_cmd = [
                str(self.las_tools_dir / "las2las64"),
                "-i", str(las_file),
                "-o", str(output_path),
                "-inside",
                xy_region,
            ]
            subprocess.run(las2las_cmd, check=True)

        print("[city4cfd] Transforming and classifying LAS data...")
        process_las_parallel(
            source_las_dir=str(subset_las_dir),
            proj_fname=str(proj_fname),
            subset_geojson=str(self.ppcfd_results / "influenceRegion.geojson"),
            target_dir=str(self.ppcfd_results),
            num_workers=num_workers,
        )

        print("[city4cfd] Merging LAS files and subsampling...")
        merge_las_files(
            source_dir=self.ppcfd_results,
            target_dir=self.ppcfd_results,
            sample_fraction=subsample_fraction,
        )

        print("[city4cfd] Pre-processing complete!")

    def run_mesher(self) -> None:
        """Execute city4cfd binary."""
        import subprocess

        config_path = self.city4cfd_dir / "config_bpg.json"
        results_dir = self.city4cfd_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        print(f"[city4cfd] Running city4cfd with config: {config_path}")
        cmd = [
            str(self.city4cfd_bin),
            str(config_path),
            "--output_dir",
            str(results_dir),
        ]
        subprocess.run(cmd, check=True, cwd=str(self.case_dir))

    def copy_results(self) -> None:
        """Copy generated STL files to constant/triSurface."""
        self.tri_surface.mkdir(parents=True, exist_ok=True)

        results_dir = self.city4cfd_dir / "results"

        building_stl = results_dir / "Mesh_Buildings.stl"
        terrain_stl = results_dir / "Mesh_Terrain.stl"

        if building_stl.exists():
            shutil.copy(building_stl, self.tri_surface / "Mesh_Buildings.stl")
            print(f"[city4cfd] Copied {building_stl} -> {self.tri_surface}")

        if terrain_stl.exists():
            shutil.copy(terrain_stl, self.tri_surface / "Mesh_Terrain.stl")
            print(f"[city4cfd] Copied {terrain_stl} -> {self.tri_surface}")

    def run_all(
        self,
        proj_fname: Path | str,
        lon0: float,
        lat0: float,
        building_footprint_source: Path | str,
        las_source_dir: Path | str,
        las_proj_fname: Path | str,
        **prep_kwargs,
    ) -> None:
        """Run full city4cfd workflow (prep + meshing + copy).

        Args:
            proj_fname: Path to PROJ string file
            lon0: Longitude of center point
            lat0: Latitude of center point
            building_footprint_source: Path to source building footprints CSV
            las_source_dir: Directory containing source LAS tiles
            las_proj_fname: Path to LAS file CRS (WKT format)
            **prep_kwargs: Additional arguments for run_prep()
        """
        self.run_prep(
            proj_fname=proj_fname,
            lon0=lon0,
            lat0=lat0,
            building_footprint_source=building_footprint_source,
            las_source_dir=las_source_dir,
            las_proj_fname=las_proj_fname,
            **prep_kwargs,
        )
        self.generate_config()
        self.run_mesher()
        self.copy_results()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="crocus city4cfd",
        description="Run city4cfd mesh generation workflow",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    prep_parser = subparsers.add_parser("prep", help="Run pre-processing only")
    prep_parser.add_argument("--case", required=True, help="Case directory")
    prep_parser.add_argument("--proj_fname", required=True)
    prep_parser.add_argument("--lon0", type=float, required=True)
    prep_parser.add_argument("--lat0", type=float, required=True)
    prep_parser.add_argument("--building_footprint_source", required=True)
    prep_parser.add_argument("--las_source_dir", required=True)
    prep_parser.add_argument("--las_proj_fname", required=True)
    prep_parser.add_argument("--building_buffer", type=float, default=600)
    prep_parser.add_argument("--domain_buffer", type=float, default=1500)
    prep_parser.add_argument("--num_workers", type=int, default=4)

    mesh_parser = subparsers.add_parser("mesh", help="Run meshing only")
    mesh_parser.add_argument("--case", required=True, help="Case directory")

    run_parser = subparsers.add_parser("run", help="Run full workflow")
    run_parser.add_argument("--case", required=True, help="Case directory")
    run_parser.add_argument("--proj_fname", required=True)
    run_parser.add_argument("--lon0", type=float, required=True)
    run_parser.add_argument("--lat0", type=float, required=True)
    run_parser.add_argument("--building_footprint_source", required=True)
    run_parser.add_argument("--las_source_dir", required=True)
    run_parser.add_argument("--las_proj_fname", required=True)
    run_parser.add_argument("--num_workers", type=int, default=4)

    args = parser.parse_args()

    runner = City4CFDRunner(case_dir=args.case)

    if args.command == "prep":
        runner.run_prep(
            proj_fname=args.proj_fname,
            lon0=args.lon0,
            lat0=args.lat0,
            building_footprint_source=args.building_footprint_source,
            las_source_dir=args.las_source_dir,
            las_proj_fname=args.las_proj_fname,
            building_buffer=args.building_buffer,
            domain_buffer=args.domain_buffer,
            num_workers=args.num_workers,
        )
    elif args.command == "mesh":
        runner.run_mesher()
    elif args.command == "run":
        runner.run_all(
            proj_fname=args.proj_fname,
            lon0=args.lon0,
            lat0=args.lat0,
            building_footprint_source=args.building_footprint_source,
            las_source_dir=args.las_source_dir,
            las_proj_fname=args.las_proj_fname,
        )


if __name__ == "__main__":
    main()