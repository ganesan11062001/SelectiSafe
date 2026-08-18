#!/usr/bin/env python3
"""Run all five agents in sequence: generate -> dock -> rescore -> retrosynthesis -> ADMET.

Each stage is its own SLURM job (submitted via `sbatch --wait`), so a failure
in one stage stops the pipeline with that stage's log path rather than
silently continuing on incomplete data.

Usage:
    python run_pipeline.py --pdb target.pdb --ligand ref_ligand.sdf --run-id my_run
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import config
from agents import (
    admet_agent,
    chem_utils,
    docking_agent,
    generation_agent,
    gnina_agent,
    retrosynthesis_agent,
)
from agents.sdf_utils import record_tags, split_records, write_per_molecule_files

RUNS_ROOT = Path(__file__).parent / "runs"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdb", required=True, help="Target protein PDB file")
    parser.add_argument("--ligand", required=True, help="Reference ligand SDF (defines the pocket)")
    parser.add_argument("--run-id", required=True, help="Name for this run's output directory")
    parser.add_argument("--n-molecules", type=int, default=50)
    parser.add_argument("--n-gpus", type=int, default=1)
    args = parser.parse_args()

    run_dir = RUNS_ROOT / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] generation (FlowR) -> {run_dir / 'generation'}")
    generated_sdf = generation_agent.run(
        pdb_file=args.pdb,
        ligand_file=args.ligand,
        save_dir=run_dir / "generation",
        run_dir=run_dir,
        n_molecules=args.n_molecules,
        n_gpus=args.n_gpus,
    )

    records = split_records(generated_sdf)
    affinity_tags = {}
    ligand_files = write_per_molecule_files(generated_sdf, run_dir / "ligands")
    for record, ligand_path in zip(records, ligand_files):
        affinity_tags[ligand_path.stem] = record_tags(record)
    print(f"  split into {len(ligand_files)} molecules")

    print(f"[2/5] docking (DiffDock) -> {run_dir / 'docking'}")
    ligand_map = {path.stem: path for path in ligand_files}
    best_poses = docking_agent.run(
        protein_path=args.pdb,
        ligand_files=ligand_map,
        out_dir=run_dir / "docking",
        run_dir=run_dir,
    )

    print(f"[3/5] rescoring (GNINA) -> {run_dir / 'gnina'}")
    rescored = gnina_agent.run(
        protein_path=args.pdb,
        poses={name: pose.path for name, pose in best_poses.items()},
        out_dir=run_dir / "gnina",
        run_dir=run_dir,
    )

    print("  extracting SMILES from generated 3D structures")
    smiles_csv = chem_utils.smiles_from_sdf_files(ligand_files, run_dir / "smiles.csv")

    print(f"[4/5] retrosynthesis (AiZynthFinder) -> {run_dir / 'retro_output.json.gz'}")
    retro_results = retrosynthesis_agent.run(smiles_csv, run_dir)
    retro_by_smiles = {r.get("target"): r for r in retro_results if isinstance(r, dict)}

    print(f"[5/5] ADMET (ADMET-AI) -> {run_dir / 'admet_predictions.csv'}")
    admet_results = admet_agent.run(smiles_csv, run_dir)

    with open(smiles_csv, newline="") as fh:
        smiles_rows = {row["complex_name"]: row["smiles"] for row in csv.DictReader(fh)}

    report_path = run_dir / "final_report.json"
    report = []
    for name in ligand_map:
        smiles = smiles_rows.get(name, "")
        pose = best_poses.get(name)
        rescore = rescored.get(name)
        report.append(
            {
                "complex_name": name,
                "smiles": smiles,
                "flowr_predicted_affinity": affinity_tags.get(name, {}),
                "docking_confidence": pose.confidence if pose else None,
                "docking_pose_path": str(pose.path) if pose else None,
                "gnina_cnn_score": rescore.cnn_score if rescore else None,
                "gnina_cnn_affinity": rescore.cnn_affinity if rescore else None,
                "gnina_minimized_affinity": rescore.minimized_affinity if rescore else None,
                "retrosynthesis": retro_by_smiles.get(smiles),
                "admet": admet_results.get(name) or admet_results.get(smiles),
            }
        )
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\ndone: {len(report)} candidates -> {report_path}")


if __name__ == "__main__":
    main()
