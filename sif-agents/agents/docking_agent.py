"""Docking agent: scores generated ligands against a target with DiffDock (diffdock-v1.0.sif).

Command mirrors selectisafe/scripts/run_diffdock_inference.sh. Two details
carried over on purpose:

* The job's `chdir` is `config.DIFFDOCK_CHDIR` (the selectisafe root), not this
  project. DiffDock caches SO(3)/torus lookup tables relative to cwd, and those
  tables already exist there (~400MB) -- launching elsewhere regenerates them.
* `--protein_ligand_csv` only reads one molecule per row: a row's
  `ligand_description` must point at a single-molecule file, matching what
  `sdf_utils.write_per_molecule_files` produces from a FlowR batch.

DiffDock does not write a machine-readable summary -- confidence rides in the
pose filename instead, e.g. `<complex>/rank1_confidence1.11.sdf`.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import config
from agents.base import SlurmJob, run_job

_POSE_RE = re.compile(r"^rank(?P<rank>\d+)_confidence(?P<conf>-?\d+\.\d+)\.sdf$")


class DockingError(RuntimeError):
    pass


@dataclass(frozen=True)
class DockedPose:
    complex_name: str
    rank: int
    confidence: float
    path: Path


def write_docking_csv(
    csv_path: str | Path, protein_path: str | Path, ligand_files: dict[str, Path]
) -> Path:
    """One row per molecule: complex_name, protein_path, ligand_description, protein_sequence."""
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["complex_name", "protein_path", "ligand_description", "protein_sequence"])
        for complex_name, ligand_path in ligand_files.items():
            writer.writerow([complex_name, str(protein_path), str(ligand_path), ""])
    return csv_path


def parse_poses(result_dir: str | Path) -> list[DockedPose]:
    """Read every ranked pose DiffDock wrote under `result_dir`."""
    root = Path(result_dir)
    if not root.is_dir():
        return []
    poses: list[DockedPose] = []
    for complex_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for sdf in sorted(complex_dir.iterdir()):
            match = _POSE_RE.match(sdf.name)
            if match is None:
                continue
            poses.append(
                DockedPose(
                    complex_name=complex_dir.name,
                    rank=int(match.group("rank")),
                    confidence=float(match.group("conf")),
                    path=sdf,
                )
            )
    return poses


def best_pose_per_complex(poses: list[DockedPose]) -> dict[str, DockedPose]:
    best: dict[str, DockedPose] = {}
    for pose in poses:
        current = best.get(pose.complex_name)
        if current is None or pose.confidence > current.confidence:
            best[pose.complex_name] = pose
    return best


def run(
    protein_path: str | Path,
    ligand_files: dict[str, Path],
    out_dir: str | Path,
    run_dir: str | Path,
) -> dict[str, DockedPose]:
    """Dock every (complex_name -> single-molecule sdf) pair in `ligand_files`.

    Returns the best (highest-confidence) pose per complex_name.
    """
    out_dir, run_dir = Path(out_dir), Path(run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = write_docking_csv(run_dir / "docking_input.csv", protein_path, ligand_files)

    command = (
        f"apptainer exec --nv -B {config.APPTAINER_BIND} {config.DIFFDOCK_SIF} "
        f"/home/appuser/micromamba/envs/diffdock/bin/python /home/appuser/DiffDock/inference.py "
        f"--config /home/appuser/DiffDock/default_inference_args.yaml "
        f"--protein_ligand_csv {csv_path} --out_dir {out_dir}"
    )

    job = SlurmJob(
        name="agent-docking",
        command=command,
        log_dir=run_dir / "logs",
        partition=config.GPU_PARTITION,
        account=config.ACCOUNT,
        time=config.GPU_WALLTIME,
        gres=config.gpu_gres(1),
        exclude=config.GPU_EXCLUDE,
        chdir=config.DIFFDOCK_CHDIR,
    )
    run_job(job, run_dir / "jobs" / "docking.sh")

    poses = parse_poses(out_dir)
    if not poses:
        raise DockingError(f"docking job reported success but wrote no poses under {out_dir}")
    return best_pose_per_complex(poses)
