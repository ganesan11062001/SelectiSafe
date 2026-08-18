"""Load candidate molecules for the Results Gallery, from either data source.

Two sources feed the same page:

* **This project's own pipeline runs** (`runs/<run_id>/final_report.json`) --
  the full 5-agent output: docking confidence, GNINA rescoring, retrosynthesis,
  ADMET.
* **The reference example** (`../selectisafe/Nithish/`) -- a colleague's
  manually-run FlowR/DiffDock/AiZynthFinder pipeline on EGFR (PDB 4ZAU,
  osimertinib), documented end-to-end with real caveats (docking failed its
  own self-docking control on this covalent-drug target -- see its READMEs).
  Only FlowR pIC50 and DiffDock confidence exist for this one; retrosynthesis
  was never run to completion, so those fields are left as None rather than
  invented.

Both loaders return the same shape so the page doesn't need to know which
source it's showing:

    {
        "id": str,
        "smiles": str | None,
        "pic50": float | None,
        "docking_confidence": float | None,
        "gnina_cnn_score": float | None,
        "retro_solved": bool | None,
        "admet": dict | None,
        "pose_sdf": str | None,     # a real 3D pose, for the 3D viewer
        "ligand_sdf": str | None,   # fallback 3D coordinates if no pose
    }
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

RUNS_ROOT = Path(__file__).parent.parent / "runs"
NITHISH_ROOT = Path("/scratch/g.murugan/Pfizer/selectisafe/Nithish")


def list_pipeline_runs() -> list[str]:
    if not RUNS_ROOT.is_dir():
        return []
    return sorted(
        (p.name for p in RUNS_ROOT.iterdir() if (p / "final_report.json").is_file()),
        reverse=True,
    )


def load_pipeline_run(run_id: str) -> list[dict[str, Any]]:
    """Candidates from this project's own `runs/<run_id>/final_report.json`."""
    report = json.loads((RUNS_ROOT / run_id / "final_report.json").read_text())
    candidates = []
    for row in report:
        candidates.append(
            {
                "id": row["complex_name"],
                "smiles": row.get("smiles") or None,
                "pic50": (row.get("flowr_predicted_affinity") or {}).get("pic50"),
                "docking_confidence": row.get("docking_confidence"),
                "gnina_cnn_score": row.get("gnina_cnn_score"),
                "retro_solved": (row.get("retrosynthesis") or {}).get("is_solved"),
                "admet": row.get("admet"),
                "pose_sdf": row.get("docking_pose_path"),
                "ligand_sdf": None,
            }
        )
    return candidates


def nithish_available() -> bool:
    return (NITHISH_ROOT / "aizynthfinder" / "all_molecules_scored.csv").is_file()


def load_nithish_reference() -> list[dict[str, Any]]:
    """Candidates from the EGFR/4ZAU reference run in ../selectisafe/Nithish/.

    SMILES come from aizynthfinder/input/candidates.csv, which only covers the
    14 molecules that were actually forwarded past both filters -- for the
    other 36, smiles is left None rather than re-deriving it from the SDF (the
    generated SDFs carry 3D coordinates and affinity tags but no SMILES; see
    ../../sif-agents/agents/chem_utils.py for why that conversion needs RDKit
    in the first place). Real numeric data (pic50, docking confidence, pass
    flags) exists for all 50, from all_molecules_scored.csv.
    """
    scored_path = NITHISH_ROOT / "aizynthfinder" / "all_molecules_scored.csv"
    with open(scored_path, newline="") as fh:
        scored = {row["molecule"]: row for row in csv.DictReader(fh)}

    smiles_by_id: dict[str, str] = {}
    candidates_csv = NITHISH_ROOT / "aizynthfinder" / "input" / "candidates.csv"
    if candidates_csv.is_file():
        with open(candidates_csv, newline="") as fh:
            for row in csv.DictReader(fh):
                smiles_by_id[row["molecule"]] = row["smiles"]

    candidates = []
    for mol_id, row in scored.items():
        pose_dir = NITHISH_ROOT / "diffdock" / "output" / mol_id
        pose_sdf = None
        if pose_dir.is_dir():
            ranked = sorted(pose_dir.glob("rank1_confidence*.sdf"))
            pose_sdf = str(ranked[0]) if ranked else None
        ligand_sdf = NITHISH_ROOT / "output" / f"{mol_id}.sdf"

        candidates.append(
            {
                "id": mol_id,
                "smiles": smiles_by_id.get(mol_id),
                "pic50": float(row["pic50"]) if row.get("pic50") else None,
                "docking_confidence": (
                    float(row["diffdock_confidence"]) if row.get("diffdock_confidence") else None
                ),
                "gnina_cnn_score": None,
                "retro_solved": None,
                "admet": None,
                "pose_sdf": pose_sdf,
                "ligand_sdf": str(ligand_sdf) if ligand_sdf.is_file() else None,
            }
        )
    return sorted(candidates, key=lambda c: c["id"])
