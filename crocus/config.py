"""Configuration management for CROCUS-UES3 cases."""

import shutil
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML configuration file."""
    with open(path) as f:
        return yaml.safe_load(f)


def save_template(content: str, output_path: Path) -> None:
    """Write rendered template to output file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(content)


def render_template(template_str: str, context: dict[str, Any]) -> str:
    """Simple template renderer using Python string formatting.

    For more complex templates, considers upgrading to Jinja2.
    """
    import re

    pattern = re.compile(r"\{\{\s*([^|}]+?)\s*(?:\|[^}]*)?\s*\}\}")

    def replacer(match):
        key = match.group(1).strip()
        keys = key.split(".")
        val = context
        for k in keys:
            val = val[k]
        if isinstance(val, list):
            return "(" + " ".join(str(v) for v in val) + ")"
        if isinstance(val, bool):
            return "yes" if val else "no"
        return str(val)

    return pattern.sub(replacer, template_str)


def generate_blockMeshDict(domain: dict[str, Any], output_path: Path) -> None:
    """Generate blockMeshDict from domain configuration."""
    x = domain["x"]
    y = domain["y"]
    z = domain["z"]

    x0, x1 = x[0], x[1]
    y0, y1 = y[0], y[1]
    z0, z1 = z[0], z[1]

    nx, ny, nz = domain["cells"]

    content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      blockMeshDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

convertToMeters 1;

vertices
(
    ({x0} {y0} {z0})
    ({x1} {y0} {z0})
    ({x1} {y1} {z0})
    ({x0} {y1} {z0})
    ({x0} {y0} {z1})
    ({x1} {y0} {z1})
    ({x1} {y1} {z1})
    ({x0} {y1} {z1})
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
);

edges
(
);

boundary
(
    bottom
    {{
        type plain;
        faces ((0 3 2 1));
    }}
    top
    {{
        type plain;
        faces ((4 5 6 7));
    }}
    sides
    {{
        type plain;
        faces ((0 1 5 4) (1 2 6 5) (2 3 7 6) (3 0 4 7));
    }}
);


// ************************************************************************* //"""
    save_template(content, output_path)


def generate_controlDict(config: dict[str, Any], output_path: Path) -> None:
    """Generate controlDict from physics configuration."""
    template_path = Path(__file__).parent.parent / "config" / "templates" / "controlDict.template"
    if template_path.exists():
        with open(template_path) as f:
            template_str = f.read()
        content = render_template(template_str, config)
    else:
        solver = config.get("solver", {})
        adj_ts = solver.get("adjustTimeStep", "yes")
        adj_ts_str = "yes" if adj_ts is True else "no" if adj_ts is False else str(adj_ts).lower()
        content = f"""/*controlDict - generated*/
libs (OpenFOAM fieldFunctionObjects urbanModels);
application {solver.get("application", "buoyantBoussinesqPimpleFoam")};
startFrom {solver.get("startFrom", "latestTime")};
startTime {solver.get("startTime", 0)};
stopAt {solver.get("stopAt", "endTime")};
endTime {solver.get("endTime", 10000)};
deltaT {solver.get("deltaT", 1)};
adjustTimeStep {adj_ts_str};
maxCo {solver.get("maxCo", 0.3)};
writeControl {solver.get("writeControl", "runTime")};
writeInterval {solver.get("writeInterval", 200)};
writeFormat {solver.get("writeFormat", "binary")};
writePrecision {solver.get("writePrecision", 6)};
purgeWrite 0;
"""
    save_template(content, output_path)


def generate_decomposeParDict(config: dict[str, Any], output_path: Path) -> None:
    """Generate decomposeParDict from decomposition configuration."""
    domain = config.get("domain", {})
    if isinstance(domain, dict) and "decomposition" in domain:
        decomp = domain.get("decomposition", {})
    else:
        decomp = config.get("decomposition", {})

    content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  v2412                                 |
|   \\\\  /    A nd           | Website:  www.openfoam.com                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      decomposeParDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

numberOfSubdomains {decomp.get("nDomains", 1)};

method          {decomp.get("method", "simple")};

simpleCoeffs
{{
    n               ({decomp.get("simpleDecomN", [1, 1, 1])[0]} {decomp.get("simpleDecomN", [1, 1, 1])[1]} {decomp.get("simpleDecomN", [1, 1, 1])[2]});
    delta           0.001;
}}

// ************************************************************************* //"""
    save_template(content, output_path)


def generate_case(source_dir: Path, target_dir: Path, case_name: str = "generated") -> None:
    """Generate a complete case directory from YAML configuration.

    Args:
        source_dir: Path to config directory (e.g., config/baseCase/)
        target_dir: Target case directory
        case_name: Name for logging
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "system").mkdir(exist_ok=True)

    domain = load_yaml(source_dir / "domain.yaml")
    physics = load_yaml(source_dir / "physics.yaml")

    config = {"domain": domain, "physics": physics, "solver": physics.get("solver", {})}

    generate_blockMeshDict(domain["domain"], target_dir / "system" / "blockMeshDict")
    generate_controlDict(config, target_dir / "system" / "controlDict")
    generate_decomposeParDict(config, target_dir / "system" / "decomposeParDict")

    shutil.copy(source_dir / "meshing.yaml", target_dir / "meshing.yaml")
    shutil.copy(source_dir / "domain.yaml", target_dir / "domain.yaml")
    shutil.copy(source_dir / "physics.yaml", target_dir / "physics.yaml")

    print(f"[{case_name}] Generated case at {target_dir}")


def main():
    """CLI entry point for config generation."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate OpenFOAM case from YAML config")
    parser.add_argument("--config", required=True, help="Path to config directory")
    parser.add_argument("--output", required=True, help="Target case directory")
    parser.add_argument("--name", default="generated", help="Case name for logging")
    args = parser.parse_args()

    generate_case(Path(args.config), Path(args.output), args.name)


if __name__ == "__main__":
    main()