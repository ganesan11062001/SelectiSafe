"""SMILES extraction from FlowR's 3D SDF output.

FlowR tags each generated molecule with predicted affinities (pic50/pki/...)
but never writes a SMILES string, and DiffDock/aizynthfinder/admet-ai each
need one downstream, in different forms (docking needs the 3D SDF; the other
two need SMILES text). Rather than adding RDKit as a host dependency, this
shells out to admet-ai.sif, which already bundles RDKit, and overrides its
`admet_predict` entrypoint with a one-off `python -c` conversion script.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import config

_CONVERT_SCRIPT = """
import csv, sys
from rdkit import Chem

out_path, sdf_paths = sys.argv[1], sys.argv[2:]
with open(out_path, "w", newline="") as fh:
    writer = csv.writer(fh)
    writer.writerow(["complex_name", "smiles"])
    for sdf_path in sdf_paths:
        mol = Chem.MolFromMolFile(sdf_path, sanitize=True)
        name = sdf_path.rsplit("/", 1)[-1].removesuffix(".sdf")
        smiles = Chem.MolToSmiles(mol) if mol is not None else ""
        writer.writerow([name, smiles])
"""


class SmilesExtractionError(RuntimeError):
    pass


def smiles_from_sdf_files(sdf_files: list[Path], out_csv: str | Path) -> Path:
    """Write a `complex_name,smiles` CSV for every single-molecule SDF in `sdf_files`.

    A molecule RDKit cannot parse gets an empty `smiles` field rather than
    aborting the batch; check the output for blanks before trusting it.
    """
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    script_path = out_csv.parent / "_sdf_to_smiles.py"
    script_path.write_text(_CONVERT_SCRIPT)

    command = [
        "apptainer",
        "exec",
        "-B",
        config.APPTAINER_BIND,
        str(config.ADMET_SIF),
        "python",
        str(script_path),
        str(out_csv),
    ] + [str(p) for p in sdf_files]

    result = subprocess.run(command)
    if result.returncode != 0 or not out_csv.is_file():
        raise SmilesExtractionError(
            f"SMILES extraction failed (exit {result.returncode}); ran: {' '.join(command)}"
        )
    return out_csv
