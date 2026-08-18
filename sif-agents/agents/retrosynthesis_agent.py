"""Retrosynthesis agent: checks synthetic accessibility with AiZynthFinder (aizynthfinder.sif).

`--smiles`, `--config`, and `--output` are confirmed against the real
`aizynthcli` argparser (MolecularAI/aizynthfinder,
aizynthfinder/interfaces/aizynthcli.py).

A real run confirmed a second gap this same reasoning missed: the image's own
PATH (`/opt/conda/bin`, from its OCI labels) does not include `aizynthcli` --
`apptainer exec ... aizynthcli` fails with `FATAL: "aizynthcli": executable
file not found in $PATH`. The upstream README's own install instructions
(`conda create -n aizynth-env`) suggest it's installed into a *named* conda
env, not the base one, but `strings` on the image can't see which name --
squashfs contents are compressed, so only the small uncompressed OCI-metadata
blob near the file's start was ever readable that way. Rather than guess a
name, the wrapper searches every `/opt/conda/envs/*/bin` for the binary at run
time and prepends whichever one has it to PATH. (It turned out to be
`/opt/conda/envs/aizynthfinder`, not the README's example name.)

A third, more fundamental problem surfaced once `aizynthcli` actually started:
`rdkit`/`sklearn` in that env are compiled against NumPy 1.x's C-API, but
NumPy 2.2.6 is what's installed -- a real ABI mismatch baked into this
third-party image (`AttributeError: _ARRAY_API not found`; the error's own
text names the fix: `downgrade to 'numpy<2'`). The wrapper pip-installs a
`numpy<2` build into `config.AIZYNTHFINDER_NUMPY_FIX` using the *container's
own* `pip` (so the build matches its Python's ABI) the first time, then
prepends that directory via `PYTHONPATH` on every run so it shadows the
broken site-packages numpy without needing to touch the read-only image.

A fourth gap surfaced once numpy was fixed and `aizynthcli` actually started:
`AiZynthFinder(configfile=...)` raised `FileNotFoundError` for
`/opt/aizynthfinder/config.yml` -- that guessed path (based on
`AIZYNTHFINDER_HOME=/opt/aizynthfinder` and the image bundling USPTO template
files, matching the layout `download_public_data` produces upstream) was
wrong; the real file is somewhere else under that tree. Same fix pattern as
PATH: the wrapper searches for `config.yml`/`config.yaml` under
`/opt/aizynthfinder` at run time instead of assuming a path, and passes
whatever it finds as `--config`. `_build_command` no longer passes `--config`
itself.

Output parsing matches `aizynthfinder.utils.files.save_datafile`: multi-SMILES
runs are written with `pandas.DataFrame.to_json(orient="table")`, which is a
plain-JSON `{"schema": ..., "data": [...]}` structure (gzip is transparent,
inferred from the `.gz` suffix) -- so it is read here as-is, with no pandas
dependency needed. Each row in `data` is one target's stats, keyed by `target`
(the SMILES) and including `is_solved` (aizynthfinder/aizynthfinder.py,
`extract_statistics`).

CPU-only: aizynthfinder's Monte-Carlo tree search does not use a GPU.
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

import config
from agents.base import SlurmJob, run_job


class RetrosynthesisError(RuntimeError):
    pass


def write_smiles_file(smiles_csv: str | Path, out_path: str | Path) -> Path:
    """aizynthcli takes a plain-text file of one SMILES per line."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(smiles_csv, newline="") as fh:
        rows = list(csv.DictReader(fh))
    out_path.write_text("\n".join(row["smiles"] for row in rows if row.get("smiles")) + "\n")
    return out_path


_FIND_AND_RUN = """#!/bin/bash
set -euo pipefail
# aizynthcli is not on the image's base PATH; it lives in some named conda
# env (upstream's own docs suggest one exists, e.g. "aizynth-env", but the
# exact name isn't confirmed) -- search for it rather than guess the name.
hit=$(find /opt/conda/envs -maxdepth 2 -type d -name bin 2>/dev/null \\
      | while read -r d; do [ -x "$d/aizynthcli" ] && echo "$d" && break; done) || true
if [ -n "$hit" ]; then
    export PATH="$hit:$PATH"
fi

# The env's rdkit/sklearn are compiled against NumPy 1.x's C-API but NumPy
# 2.2.6 is installed -- a real ABI mismatch in this image. Fix once, reuse
# after: pip-install a numpy<2 build with this env's own pip (matching its
# Python's ABI) into FIX_DIR, then shadow the broken numpy via PYTHONPATH.
FIX_DIR="{fix_dir}"
if [ ! -d "$FIX_DIR/numpy" ]; then
    mkdir -p "$FIX_DIR"
    "$(dirname "$(command -v aizynthcli)")/pip" install --quiet --target "$FIX_DIR" 'numpy<2'
fi
export PYTHONPATH="$FIX_DIR:${{PYTHONPATH:-}}"

# config.yml's path inside this image isn't confirmed. First guess
# (/opt/aizynthfinder/config.yml, maxdepth 3) was wrong; broadening to any
# *.yml/*.yaml matched the WRONG file (/opt/aizynthfinder/env-dev.yml -- the
# repo's own conda dev-environment file, not an aizynthfinder config: it
# parsed as valid YAML but had no stock/policy data, so the run "succeeded"
# with 0 compounds in stock and then crashed selecting policy [0] of an empty
# list). Configuration.from_dict (aizynthfinder/context/config.py) pops
# "expansion"/"filter"/"stock"/"scorer" as top-level keys -- confirmed from
# that source directly -- so candidates are now filtered by content, not just
# filename: only a file with an unindented "stock:" or "expansion:" line
# qualifies.
cfg=""
for candidate in $(find /opt/aizynthfinder /opt /data -maxdepth 6 \\( -iname "*.yml" -o -iname "*.yaml" \\) 2>/dev/null); do
    if grep -qE '^(stock|expansion):' "$candidate" 2>/dev/null; then
        cfg="$candidate"
        break
    fi
done
if [ -z "$cfg" ]; then
    echo "FATAL: no yml/yaml with a top-level stock:/expansion: key found under /opt/aizynthfinder, /opt, or /data" >&2
    echo ">>> diagnostic: contents of /opt/aizynthfinder (depth 4):" >&2
    find /opt/aizynthfinder -maxdepth 4 >&2 || true
    echo ">>> diagnostic: contents of AIZYNTHFINDER_HOME env var target, if different:" >&2
    ( [ -n "${{AIZYNTHFINDER_HOME:-}}" ] && find "$AIZYNTHFINDER_HOME" -maxdepth 4 >&2 ) || true
    exit 3
fi
echo ">>> using aizynthfinder config: $cfg" >&2

exec aizynthcli --config "$cfg" "$@"
"""


def _write_wrapper(run_dir: Path) -> Path:
    path = run_dir / "jobs" / "_run_aizynthcli.sh"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_FIND_AND_RUN.format(fix_dir=config.AIZYNTHFINDER_NUMPY_FIX))
    path.chmod(0o755)
    return path


def _build_command(wrapper: Path, smiles_file: Path, out_json: Path) -> str:
    # wrapper/smiles_file/out_json all live under run_dir, already covered by
    # config.APPTAINER_BIND's /scratch:/scratch -- no extra -B needed for them.
    # No --config here: the wrapper discovers the real config path itself.
    return (
        f"apptainer exec -B {config.APPTAINER_BIND} {config.AIZYNTHFINDER_SIF} "
        f"bash {wrapper} "
        f"--smiles {smiles_file} --output {out_json}"
    )


def parse_results(out_json: str | Path) -> list[dict]:
    """Read aizynthcli's per-target stats from a pandas table-orient JSON file.

    Drops the `trees` field: aizynthcli embeds the full route tree (with
    metadata and scores) in every row, which alone runs to ~47,000 characters
    per candidate -- fine on disk (still in `out_json` itself, untouched), but
    it blew a real Ollama analysis prompt out to 878,621 characters and past
    Ollama's own request timeout. `is_solved` and the other tree-search stats
    say everything the summary/report actually need; the trees are still on
    disk in `out_json` for anything that wants to render an actual route.
    """
    path = Path(out_json)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as fh:
        data = json.load(fh)
    return [{k: v for k, v in row.items() if k != "trees"} for row in data["data"]]


def run(smiles_csv: str | Path, run_dir: str | Path) -> list[dict]:
    """Run retrosynthesis planning on every SMILES in `smiles_csv` (complex_name,smiles)."""
    smiles_csv, run_dir = Path(smiles_csv), Path(run_dir)
    smiles_file = write_smiles_file(smiles_csv, run_dir / "retro_input.smi")
    out_json = run_dir / "retro_output.json.gz"
    wrapper = _write_wrapper(run_dir)

    job = SlurmJob(
        name="agent-retrosynthesis",
        command=_build_command(wrapper, smiles_file, out_json),
        log_dir=run_dir / "logs",
        partition=config.CPU_PARTITION,
        account=config.ACCOUNT,
        time=config.CPU_WALLTIME,
        cpus=4,
        mem="8GB",
    )
    run_job(job, run_dir / "jobs" / "retrosynthesis.sh")

    if not out_json.is_file():
        raise RetrosynthesisError(
            f"aizynthfinder job reported success but wrote no output at {out_json}"
        )
    return parse_results(out_json)
