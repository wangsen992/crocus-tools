"""
CROCUS CLI - Command line interface for CROCUS-UES3 tools.
"""

import argparse
import sys
from pathlib import Path


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="crocus",
        description="Urban CFD simulation tools for CROCUS-UES3"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    canopy_parser = subparsers.add_parser("canopy", help="Canopy LAD processing")
    canopy_parser.add_argument("--veg_dir", default="ppcfd_results/vegetation_las")
    canopy_parser.add_argument("--gnd_dir", default="ppcfd_results/ground_las")
    canopy_parser.add_argument("--output", default="constant/urban/point_data/lad")
    canopy_parser.add_argument("--num_workers", type=int, default=4)
    canopy_parser.add_argument("--spacing", type=float, default=0.5)

    geometry_parser = subparsers.add_parser("geometry", help="Geometry processing")
    geometry_parser.add_argument("--lon0", type=float, required=True)
    geometry_parser.add_argument("--lat0", type=float, required=True)
    geometry_parser.add_argument("--building_buffer", type=int, default=200)
    geometry_parser.add_argument("--domain_buffer", type=int, default=300)
    geometry_parser.add_argument("--proj_fname", default="proj4str.txt")
    geometry_parser.add_argument("--target_dir", default="./results")

    boundaries_parser = subparsers.add_parser("boundaries", help="Create boundary GeoJSONs")
    boundaries_parser.add_argument("--proj_fname", default="proj4str.txt")
    boundaries_parser.add_argument("--lon0", type=float, required=True)
    boundaries_parser.add_argument("--lat0", type=float, required=True)
    boundaries_parser.add_argument("--building_buffer", type=int, default=200)
    boundaries_parser.add_argument("--domain_buffer", type=int, default=300)
    boundaries_parser.add_argument("--target_dir", default="./results")

    footprints_parser = subparsers.add_parser("footprints", help="Subset building footprints")
    footprints_parser.add_argument("--proj_fname", default="proj4str.txt")
    footprints_parser.add_argument("--source_bldfprt", required=True)
    footprints_parser.add_argument("--target_dir", default="./results")

    las_bnds_parser = subparsers.add_parser("las-bnds", help="Get LAS bounding box")
    las_bnds_parser.add_argument("--proj_fname", default="proj4str.txt")
    las_bnds_parser.add_argument("--subset_geojson", required=True)
    las_bnds_parser.add_argument("--las_proj_fname", default="las_proj.txt")

    las_parser = subparsers.add_parser("las", help="LAS file preprocessing")
    las_parser.add_argument("--source_las", required=True)
    las_parser.add_argument("--proj_fname", default="proj4str.txt")
    las_parser.add_argument("--subset_geojson", required=True)
    las_parser.add_argument("--target_dir", default="./results")
    las_parser.add_argument("--num_workers", type=int, default=4)

    viz_parser = subparsers.add_parser("viz", help="VTK visualization")
    viz_parser.add_argument("--surface_dir", default="postProcessing/surfaces/")
    viz_parser.add_argument("--fname", required=True)
    viz_parser.add_argument("--vname", required=True)
    viz_parser.add_argument("--movie_name")
    viz_parser.add_argument("--max_files", type=int)

    city4cfd_parser = subparsers.add_parser("city4cfd", help="city4cfd mesh generation")
    city4cfd_subparsers = city4cfd_parser.add_subparsers(dest="city4cfd_command")

    prep_parser = city4cfd_subparsers.add_parser("prep", help="Run pre-processing only")
    prep_parser.add_argument("--case", required=True)
    prep_parser.add_argument("--proj_fname", required=True)
    prep_parser.add_argument("--lon0", type=float, required=True)
    prep_parser.add_argument("--lat0", type=float, required=True)
    prep_parser.add_argument("--building_footprint_source", required=True)
    prep_parser.add_argument("--las_source_dir", required=True)
    prep_parser.add_argument("--las_proj_fname", required=True)
    prep_parser.add_argument("--building_buffer", type=float, default=600)
    prep_parser.add_argument("--domain_buffer", type=float, default=1500)
    prep_parser.add_argument("--num_workers", type=int, default=4)

    mesh_parser = city4cfd_subparsers.add_parser("mesh", help="Run meshing only")
    mesh_parser.add_argument("--case", required=True)

    run_parser = city4cfd_subparsers.add_parser("run", help="Run full workflow")
    run_parser.add_argument("--case", required=True)
    run_parser.add_argument("--proj_fname", required=True)
    run_parser.add_argument("--lon0", type=float, required=True)
    run_parser.add_argument("--lat0", type=float, required=True)
    run_parser.add_argument("--building_footprint_source", required=True)
    run_parser.add_argument("--las_source_dir", required=True)
    run_parser.add_argument("--las_proj_fname", required=True)
    run_parser.add_argument("--num_workers", type=int, default=4)

    args = parser.parse_args()

    if args.command == "canopy":
        from crocus.canopy import voxelize_las
        voxelize_las(args.veg_dir, args.gnd_dir, args.output,
                     args.num_workers, args.spacing)
        print(f"Canopy processing complete: {args.output}")

    elif args.command == "geometry":
        from crocus.geometry import create_bounds
        result = create_bounds(args.lon0, args.lat0,
                              args.building_buffer, args.domain_buffer,
                              args.proj_fname, args.target_dir)
        print(f"Geometry processing complete: {result}")

    elif args.command == "boundaries":
        from crocus.boundaries import create_boundaries
        influence_path, domain_path = create_boundaries(
            proj_fname=args.proj_fname,
            lon0=args.lon0,
            lat0=args.lat0,
            building_buffer=args.building_buffer,
            domain_buffer=args.domain_buffer,
            target_dir=args.target_dir,
        )
        print(f"Created: {influence_path}, {domain_path}")

    elif args.command == "footprints":
        from crocus.footprints import subset_building_footprints
        output_path = subset_building_footprints(
            proj_fname=args.proj_fname,
            source_bldfprt=args.source_bldfprt,
            target_dir=args.target_dir,
        )
        print(f"Created: {output_path}")

    elif args.command == "las-bnds":
        from crocus.las_bnds import get_las_bounding_box
        result = get_las_bounding_box(
            proj_fname=args.proj_fname,
            subset_geojson=args.subset_geojson,
            las_proj_fname=args.las_proj_fname,
        )
        print(result)

    elif args.command == "las":
        from crocus.las_prep import process_las_parallel
        source_path = Path(args.source_las)
        if source_path.is_dir():
            process_las_parallel(args.source_las, args.proj_fname,
                                 args.subset_geojson, args.target_dir,
                                 args.num_workers)
            print(f"Processed LAS files in {args.source_las}")
        else:
            from crocus.las_prep import process_las_file
            result = process_las_file(source_path, args.proj_fname,
                                      args.subset_geojson, Path(args.target_dir))
            print(f"Processed: {result}")

    elif args.command == "viz":
        from crocus.visualization import animate_surface
        animate_surface(args.surface_dir, args.fname, args.vname,
                        args.movie_name, args.max_files)
        print(f"Visualization complete: {args.movie_name}")

    elif args.command == "city4cfd":
        from crocus.city4cfd import City4CFDRunner
        runner = City4CFDRunner(case_dir=args.case)

        if args.city4cfd_command == "prep":
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
            print("[city4cfd] Pre-processing complete")
        elif args.city4cfd_command == "mesh":
            runner.run_mesher()
            print("[city4cfd] Meshing complete")
        elif args.city4cfd_command == "run":
            runner.run_all(
                proj_fname=args.proj_fname,
                lon0=args.lon0,
                lat0=args.lat0,
                building_footprint_source=args.building_footprint_source,
                las_source_dir=args.las_source_dir,
                las_proj_fname=args.las_proj_fname,
            )
            print("[city4cfd] Full workflow complete")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()