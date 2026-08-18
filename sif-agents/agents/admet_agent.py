"""ADMET agent: predicts pharmacokinetic/safety properties with ADMET-AI (admet-ai.sif).

`--data_path`/`--save_path`/`--smiles_column` are confirmed against the real
README (swansonk14/admet_ai) -- this is the exact example command it
documents for the `admet_predict` CLI, and the image's own metadata confirms
that entrypoint is on PATH. What is *not* confirmed is whether `admet_predict`
carries the `complex_name` input column through to the output CSV alongside
its predictions (the README only documents the `smiles` column); `run()`
below falls back to keying by `smiles` if `complex_name` did not survive.

CPU-only: admet-ai's ensemble models are small enough that a GPU adds nothing
worth a `gpu` partition queue wait.
"""

from __future__ import annotations

import csv
from pathlib import Path

import config
from agents.base import SlurmJob, run_job


class AdmetError(RuntimeError):
    pass


def _build_command(smiles_csv: Path, out_csv: Path) -> str:
    return (
        f"apptainer exec -B {config.APPTAINER_BIND} {config.ADMET_SIF} admet_predict "
        f"--data_path {smiles_csv} --smiles_column smiles --save_path {out_csv}"
    )


def run(smiles_csv: str | Path, run_dir: str | Path) -> dict[str, dict[str, str]]:
    """Predict ADMET properties for every row of `smiles_csv` (complex_name,smiles).

    Returns {complex_name: {property: value, ...}} parsed from admet-ai's output CSV.
    """
    smiles_csv, run_dir = Path(smiles_csv), Path(run_dir)
    out_csv = run_dir / "admet_predictions.csv"

    job = SlurmJob(
        name="agent-admet",
        command=_build_command(smiles_csv, out_csv),
        log_dir=run_dir / "logs",
        partition=config.CPU_PARTITION,
        account=config.ACCOUNT,
        time=config.CPU_WALLTIME,
        cpus=4,
        mem="8GB",
    )
    run_job(job, run_dir / "jobs" / "admet.sh")

    if not out_csv.is_file():
        raise AdmetError(f"admet-ai job reported success but wrote no output at {out_csv}")

    with open(out_csv, newline="") as fh:
        rows = list(csv.DictReader(fh))
    key = "complex_name" if rows and "complex_name" in rows[0] else "smiles"
    return {row[key]: row for row in rows}
