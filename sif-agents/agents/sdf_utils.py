"""Pure-Python helpers for FlowR/DiffDock SDF records — no RDKit required.

FlowR writes an entire generation batch into one multi-record SDF and tags
each record with predicted affinities (pic50/pki/pkd/pec50) rather than a
SMILES string. DiffDock's --protein_ligand_csv only reads the first record of
a multi-molecule file, so the batch must be split into one file per molecule
before docking.
"""

from __future__ import annotations

import re
from pathlib import Path

_SDF_TERMINATOR = "$$$$"
_TAG_RE = re.compile(r"^>\s*<(\w+)>.*\n(.+)$", re.MULTILINE)


def split_records(sdf_path: str | Path) -> list[str]:
    """Split a multi-molecule SDF into whole records, tags intact."""
    text = Path(sdf_path).read_text()
    records: list[str] = []
    current: list[str] = []
    for line in text.splitlines(keepends=True):
        current.append(line)
        if line.startswith(_SDF_TERMINATOR):
            records.append("".join(current))
            current = []
    if any(line.strip() for line in current):
        raise ValueError(f"{sdf_path} has trailing data after the last {_SDF_TERMINATOR}")
    if not records:
        raise ValueError(f"{sdf_path} contains no SDF records")
    return records


def record_title(record: str) -> str:
    """First line of an SDF record; FlowR writes it as `<pdb_stem>_<index>`."""
    return record.split("\n", 1)[0].strip()


def record_tags(record: str) -> dict[str, float]:
    """Numeric property tags on a record, e.g. FlowR's pic50/pki/pkd/pec50."""
    tags: dict[str, float] = {}
    for name, value in _TAG_RE.findall(record):
        try:
            tags[name] = float(value.strip())
        except ValueError:
            continue
    return tags


def write_per_molecule_files(sdf_path: str | Path, out_dir: str | Path) -> list[Path]:
    """Split `sdf_path` into `out_dir/<title>.sdf`, one file per molecule.

    Returns the written paths in source order, so callers can zip them back
    against `split_records`/`record_tags` results by index.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for idx, record in enumerate(split_records(sdf_path)):
        title = record_title(record) or f"mol_{idx:03d}"
        path = out / f"{title}.sdf"
        path.write_text(record)
        paths.append(path)
    return paths
