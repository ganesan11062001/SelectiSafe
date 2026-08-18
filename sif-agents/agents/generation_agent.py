"""Generation agent: samples ligands into a protein pocket with FlowR (flowr-v1.0.sif).

Command and flags mirror selectisafe/scripts/submit_flowr_inference.sh, the
FlowR invocation already verified working on this cluster. Two details carried
over on purpose:

* PYTHONPATH is passed via `--env`, not a shell export -- `--cleanenv` behavior
  means the image only sees what is passed through `--env`.
* `--gpus` is derived from `n_gpus` rather than hardcoded, so it can never
  drift from the `--gres` allocation requested below it.
"""

from __future__ import annotations

from pathlib import Path

import config
from agents.base import SlurmJob, run_job


class GenerationError(RuntimeError):
    pass


def expected_sdf_path(save_dir: str | Path, pdb_file: str | Path) -> Path:
    """FlowR writes `samples_<pdb stem>.sdf` into save_dir."""
    return Path(save_dir) / f"samples_{Path(pdb_file).stem}.sdf"


def run(
    pdb_file: str | Path,
    ligand_file: str | Path,
    save_dir: str | Path,
    run_dir: str | Path,
    n_molecules: int = 50,
    n_gpus: int = 1,
    pocket_cutoff: float = 7.0,
    diversity_threshold: float = 0.7,
) -> Path:
    """Sample `n_molecules` ligands into `pdb_file`'s pocket; return the output SDF path."""
    pdb_file, ligand_file = Path(pdb_file), Path(ligand_file)
    save_dir, run_dir = Path(save_dir), Path(run_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    command = (
        f"apptainer exec --nv -B {config.APPTAINER_BIND} "
        f"--env PYTHONPATH=/opt/flowr_root {config.FLOWR_SIF} "
        f"python -m flowr.gen.generate_from_pdb "
        f"--pdb_file {pdb_file} --ligand_file {ligand_file} "
        f"--arch pocket --pocket_type holo --cut_pocket --pocket_cutoff {pocket_cutoff} "
        f"--gpus {n_gpus} --num_workers 4 --batch_cost 20 "
        f"--ckpt_path {config.FLOWR_CKPT} --save_dir {save_dir} "
        f"--max_sample_iter 30 --coord_noise_scale 0.1 "
        f"--sample_n_molecules_per_target {n_molecules} "
        f"--categorical_strategy uniform-sample "
        f"--filter_valid_unique --filter_diversity --diversity_threshold {diversity_threshold}"
    )

    job = SlurmJob(
        name="agent-generation",
        command=command,
        log_dir=run_dir / "logs",
        partition=config.GPU_PARTITION,
        account=config.ACCOUNT,
        time=config.GPU_WALLTIME,
        gres=config.gpu_gres(n_gpus),
        exclude=config.GPU_EXCLUDE,
    )
    run_job(job, run_dir / "jobs" / "generation.sh")

    sdf_path = expected_sdf_path(save_dir, pdb_file)
    if not sdf_path.is_file():
        raise GenerationError(f"FlowR job reported success but wrote no samples at {sdf_path}")
    return sdf_path
