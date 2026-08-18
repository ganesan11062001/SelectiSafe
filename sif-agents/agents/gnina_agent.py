"""GNINA agent: rescores DiffDock's poses with CNN-based binding scores (gnina.sif).

GNINA (https://github.com/gnina/gnina, packaged from Docker Hub `gnina/gnina:latest`
per the image's OCI labels) is a single-binary docking/scoring tool -- a fork of smina/
AutoDock Vina with an integrated CNN scoring function. It can run full blind docking
(`--autobox_ligand`), but it also has a documented mode for exactly what this pipeline
needs here: scoring poses that are *already positioned*, without re-searching:

    gnina -r rec.pdb -l ligs.sdf --minimize -o minimized.sdf.gz

(README, "To minimize and score ligands already positioned in a binding site"). Using
this on DiffDock's best pose per molecule gives a second, physically-grounded CNN score
(CNNscore/CNNaffinity/minimizedAffinity) alongside DiffDock's own confidence, rather
than re-running a second independent blind docking search.

Each molecule is minimized in its own `gnina` invocation, inside one SLURM job that
loops over all poses in bash -- one call per file keeps the output identity
unambiguous (output filename = complex_name), matching how docking_agent tracks
complexes by directory name rather than parsing titles back out of a shared file.

Tag names (CNNscore/CNNaffinity/minimizedAffinity) are confirmed against the README's
`--pose_sort_order` documentation, which names exactly these three; parsing is
lenient about which end up present since `--cnn_scoring` can be set to `none`.
"""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass
from pathlib import Path

import config
from agents.base import SlurmJob, run_job

_TAG_RE = re.compile(r"^>\s*<(\w+)>.*\n(.+)$", re.MULTILINE)


class GninaError(RuntimeError):
    pass


@dataclass(frozen=True)
class RescoredPose:
    complex_name: str
    cnn_score: float | None
    cnn_affinity: float | None
    minimized_affinity: float | None
    path: Path


def _read_first_record_tags(sdf_gz_path: Path) -> dict[str, float]:
    """Tags of the top (first, best-ranked) record in a gnina output SDF."""
    with gzip.open(sdf_gz_path, "rt") as fh:
        text = fh.read()
    first_record = text.split("$$$$", 1)[0]
    tags: dict[str, float] = {}
    for name, value in _TAG_RE.findall(first_record):
        try:
            tags[name] = float(value.strip())
        except ValueError:
            continue
    return tags


def run(
    protein_path: str | Path,
    poses: dict[str, Path],
    out_dir: str | Path,
    run_dir: str | Path,
    cnn_scoring: str = "rescore",
) -> dict[str, RescoredPose]:
    """Rescore each complex_name -> docked pose file with GNINA's `--minimize` mode."""
    protein_path = Path(protein_path)
    out_dir, run_dir = Path(out_dir), Path(run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    calls = []
    outputs: dict[str, Path] = {}
    for complex_name, pose_path in poses.items():
        out_path = out_dir / f"{complex_name}.sdf.gz"
        outputs[complex_name] = out_path
        calls.append(
            f"apptainer exec --nv -B {config.APPTAINER_BIND} {config.GNINA_SIF} gnina "
            f"-r {protein_path} -l {pose_path} --minimize "
            f"--cnn_scoring {cnn_scoring} -o {out_path}"
        )
    command = "\n".join(calls)

    job = SlurmJob(
        name="agent-gnina",
        command=command,
        log_dir=run_dir / "logs",
        partition=config.GPU_PARTITION,
        account=config.ACCOUNT,
        time=config.GPU_WALLTIME,
        gres=config.gpu_gres(1),
        exclude=config.GPU_EXCLUDE,
    )
    run_job(job, run_dir / "jobs" / "gnina.sh")

    results: dict[str, RescoredPose] = {}
    for complex_name, out_path in outputs.items():
        if not out_path.is_file():
            continue
        tags = _read_first_record_tags(out_path)
        results[complex_name] = RescoredPose(
            complex_name=complex_name,
            cnn_score=tags.get("CNNscore"),
            cnn_affinity=tags.get("CNNaffinity"),
            minimized_affinity=tags.get("minimizedAffinity"),
            path=out_path,
        )

    if not results:
        raise GninaError(f"gnina job reported success but wrote no readable output under {out_dir}")
    return results
